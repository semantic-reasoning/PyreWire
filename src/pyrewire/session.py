"""High-level session wrappers over wirelog's facade APIs.

`EasySession` (this issue, #9) wraps `wirelog_easy_*`. Delta-mode
machinery (`step` / `deltas` / `set_delta_callback`) is added in #10;
query-mode `snapshot` lands in #11; `make_compound` in #23.
"""

from __future__ import annotations

import ctypes
import threading
from collections.abc import Sequence
from contextlib import AbstractContextManager
from enum import Enum
from typing import Any

from ._core.errors import ExecError, check
from ._core.intern import InternTable
from ._ffi import LIB
from ._ffi import _easy as _easy_ffi  # noqa: F401  -- registers argtypes
from ._ffi._types import (
    EASY_OPEN_OPTS_SIZE,
    EasyOpenOptsStruct,
    EasySessionHandle,
)

Value = int | str | bool | float
Row = Sequence[Value]


class _Mode(Enum):
    """Tracks which evaluation mode the session has entered. The
    transition is one-way per session: once in INCREMENTAL or QUERY,
    the other mode raises `WirelogModeError`. Used by #10 and #11; the
    lifecycle class in this issue installs the field so subclasses /
    sibling methods can read/write it consistently."""

    UNSET = 0
    INCREMENTAL = 1
    QUERY = 2


class _NullCM:
    """Context manager that does nothing — used when the session was
    constructed with `lock=False`."""

    def __enter__(self) -> _NullCM:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


class EasySession(AbstractContextManager["EasySession"]):
    """Pythonic wrapper over `wirelog_easy_*`.

    Use as a context manager:

        with EasySession(SRC) as s:
            s.insert("rel", ["alice", "bob"])

    String values are auto-interned through a per-session
    `InternTable`. Concurrent calls from multiple Python threads are
    serialised through an internal `RLock` (opt out with `lock=False`).
    """

    def __init__(
        self,
        dl_src: str,
        *,
        num_workers: int = 0,
        eager_build: bool = False,
        lock: bool = True,
    ) -> None:
        self._handle: EasySessionHandle = EasySessionHandle()
        opts = EasyOpenOptsStruct(
            size=EASY_OPEN_OPTS_SIZE,
            num_workers=int(num_workers),
            eager_build=bool(eager_build),
            _reserved=None,
        )
        rc = LIB.wirelog_easy_open_opts(
            dl_src.encode("utf-8"),
            ctypes.byref(opts),
            ctypes.byref(self._handle),
        )
        check(rc)
        if not self._handle.value:
            raise ExecError("wirelog_easy_open_opts returned a NULL handle")

        self._lock: threading.RLock | None = threading.RLock() if lock else None
        self._closed: bool = False
        self._mode: _Mode = _Mode.UNSET
        self._intern = InternTable(self._intern_raw)

    # --- intern -------------------------------------------------------------

    def _intern_raw(self, symbol_bytes: bytes) -> int:
        return int(LIB.wirelog_easy_intern(self._handle, symbol_bytes))

    def intern(self, value: str) -> int:
        """Return the id wirelog assigns to `value`. Cached after the
        first call for the same string."""
        with self._serialize():
            return self._intern.intern(value)

    # --- insert / remove ----------------------------------------------------

    def insert(self, relation: str, row: Row) -> None:
        """Insert one row. Each `str` element is auto-interned."""
        ids = self._row_to_int64(row)
        arr = (ctypes.c_int64 * len(ids))(*ids)
        with self._serialize():
            rc = LIB.wirelog_easy_insert(
                self._handle,
                relation.encode("utf-8"),
                arr,
                ctypes.c_uint32(len(ids)),
            )
        check(rc)

    def remove(self, relation: str, row: Row) -> None:
        """Retract one row (z-set multiplicity decrement by 1)."""
        ids = self._row_to_int64(row)
        arr = (ctypes.c_int64 * len(ids))(*ids)
        with self._serialize():
            rc = LIB.wirelog_easy_remove(
                self._handle,
                relation.encode("utf-8"),
                arr,
                ctypes.c_uint32(len(ids)),
            )
        check(rc)

    def _row_to_int64(self, row: Row) -> list[int]:
        out: list[int] = []
        for v in row:
            if isinstance(v, bool):
                out.append(1 if v else 0)
            elif isinstance(v, int):
                out.append(int(v))
            elif isinstance(v, float):
                # wirelog FLOAT columns travel as int64 bit-patterns at
                # the public API; round-trip through c_double / c_int64.
                out.append(ctypes.c_int64.from_buffer_copy(ctypes.c_double(v)).value)
            elif isinstance(v, str):
                out.append(self._intern.intern(v))
            else:
                raise TypeError(f"unsupported row value type: {type(v).__name__}")
        return out

    # --- lifecycle ----------------------------------------------------------

    def close(self) -> None:
        """Idempotently free the underlying wirelog handle."""
        if self._closed:
            return
        with self._lock if self._lock is not None else _NullCM():
            if self._handle.value:
                LIB.wirelog_easy_close(self._handle)
            self._handle = EasySessionHandle()
            self._closed = True

    def __exit__(self, *exc: object) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

    # --- internals ----------------------------------------------------------

    def _serialize(self) -> Any:
        """Return the lock context (no-op when `lock=False`)."""
        return self._lock if self._lock is not None else _NullCM()

    def _require_mode(self, want: _Mode) -> None:
        """One-way transition: first call commits the mode; subsequent
        calls in the other mode raise `WirelogModeError`. Used by #10
        and #11 — this issue's surface (intern/insert/remove) does not
        commit a mode by itself."""
        from ._core.errors import WirelogModeError

        if self._mode == _Mode.UNSET:
            self._mode = want
            return
        if self._mode != want:
            raise WirelogModeError(
                f"session is in {self._mode.name} mode; "
                f"{want.name} operation rejected. Close and reopen the "
                "session to switch modes."
            )


__all__ = ["EasySession"]
