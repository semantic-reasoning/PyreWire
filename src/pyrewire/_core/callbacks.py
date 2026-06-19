# SPDX-License-Identifier: Apache-2.0 OR GPL-3.0-or-later
"""Process-wide registry of callback trampolines.

wirelog invokes user callbacks from its own worker threads. Two
hard requirements that this module enforces:

1. **Strong references.** Every `CFUNCTYPE` instance and the Python
   callable it wraps must outlive the period during which wirelog
   might call into it. The module-level `_REGISTRY` plus a strong
   reference held by the owning session keeps this guarantee. Letting
   a trampoline be garbage-collected while wirelog still holds a
   pointer to it segfaults the process.

2. **No exceptions into C.** Python exceptions raised inside a
   callback must not propagate across the FFI boundary. The
   trampolines `try/except BaseException` and stash the error on
   the registry slot. `CallbackHandle.drain()` then re-raises after
   wirelog has returned control to Python.

The two trampolines (`_delta_trampoline`, `_tuple_trampoline`) are
module-level singletons. Per-session instances would multiply ctypes
overhead and complicate lifetime management.
"""

from __future__ import annotations

import ctypes
import threading
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from .._ffi._types import OnDeltaFn, OnTupleFn

# Event payloads buffered by the trampolines. The first element ("delta"
# or "tuple") is the trampoline kind; the rest is the decoded payload.
DeltaEvent = tuple[str, str, tuple[int, ...], int]  # ("delta", rel, row_ids, diff)
TupleEvent = tuple[str, str, tuple[int, ...]]  # ("tuple", rel, row_ids)
Event = Any  # union of the above


@dataclass
class _TrampolineState:
    queue: deque[Event] = field(default_factory=deque)
    user_fn: Callable[..., Any] | None = None
    last_error: BaseException | None = None


_REGISTRY: dict[int, _TrampolineState] = {}
_REGISTRY_LOCK = threading.Lock()
_NEXT_TOKEN = 1


def _next_token() -> int:
    global _NEXT_TOKEN
    with _REGISTRY_LOCK:
        token = _NEXT_TOKEN
        _NEXT_TOKEN += 1
    return token


# --- module-level trampolines ----------------------------------------------
#
# Both trampolines defensively swallow every exception. They store the
# exception on the registry slot (best effort) so `drain()` can re-raise
# it. Never let one propagate into wirelog's C call.


@OnDeltaFn  # type: ignore[untyped-decorator]
def _delta_trampoline(
    relation: bytes,
    row: ctypes._Pointer[ctypes.c_int64],
    ncols: int,
    diff: int,
    user_data: Any,
) -> None:
    state: _TrampolineState | None = None
    try:
        raw = ctypes.cast(user_data, ctypes.c_void_p).value
        token = int(raw) if raw else 0
        state = _REGISTRY.get(token)
        if state is None:
            return
        rel = relation.decode() if relation else ""
        n = int(ncols)
        values: tuple[int, ...] = tuple(int(row[i]) for i in range(n))
        state.queue.append(("delta", rel, values, int(diff)))
    except BaseException as exc:  # never propagate to C
        if state is not None:
            state.last_error = exc


@OnTupleFn  # type: ignore[untyped-decorator]
def _tuple_trampoline(
    relation: bytes,
    row: ctypes._Pointer[ctypes.c_int64],
    ncols: int,
    user_data: Any,
) -> None:
    state: _TrampolineState | None = None
    try:
        raw = ctypes.cast(user_data, ctypes.c_void_p).value
        token = int(raw) if raw else 0
        state = _REGISTRY.get(token)
        if state is None:
            return
        rel = relation.decode() if relation else ""
        n = int(ncols)
        values: tuple[int, ...] = tuple(int(row[i]) for i in range(n))
        state.queue.append(("tuple", rel, values))
    except BaseException as exc:
        if state is not None:
            state.last_error = exc


# --- public API ------------------------------------------------------------


class CallbackHandle:
    """Owns a registry slot. Pass `.user_data` to wirelog and keep this
    object alive for as long as wirelog might invoke the callback.
    """

    __slots__ = ("kind", "token", "_state", "__weakref__")

    def __init__(self, kind: str, user_fn: Callable[..., Any] | None = None) -> None:
        if kind not in ("delta", "tuple"):
            raise ValueError(f"unknown callback kind: {kind!r}")
        self.kind: str = kind
        self.token: int = _next_token()
        self._state: _TrampolineState = _TrampolineState(user_fn=user_fn)
        _REGISTRY[self.token] = self._state

    @property
    def user_data(self) -> ctypes.c_void_p:
        """Opaque token to pass to wirelog as `user_data`."""
        return ctypes.c_void_p(self.token)

    @property
    def fn(self) -> Any:
        """The module-level CFUNCTYPE instance matching `kind`."""
        return _delta_trampoline if self.kind == "delta" else _tuple_trampoline

    def drain(self) -> list[Event]:
        """Pop and return all queued events. If a callback raised, the
        exception is re-raised here after the queue is emptied."""
        events = list(self._state.queue)
        self._state.queue.clear()
        err = self._state.last_error
        if err is not None:
            self._state.last_error = None
            raise err
        return events

    def close(self) -> None:
        """Release the registry slot. Subsequent callback invocations
        with this token become no-ops."""
        _REGISTRY.pop(self.token, None)

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass


__all__ = ["CallbackHandle", "DeltaEvent", "TupleEvent", "Event"]
