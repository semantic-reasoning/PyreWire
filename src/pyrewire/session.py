"""High-level session wrappers over wirelog's facade APIs.

`EasySession` (#9) wraps `wirelog_easy_*`. `Session` (#21) wraps the
advanced `wirelog_session_*` API: caller-owned program, backend
selection, batched insert / remove, step, snapshot, delta callbacks,
and an explicit program-borrow guarantee.

Delta-mode machinery (`step` / `deltas` / `set_delta_callback`) on
`EasySession` is added in #10; query-mode `snapshot` lands in #11;
`make_compound` (advanced) in #23.
"""

from __future__ import annotations

import ctypes
import threading
from collections.abc import Callable, Sequence
from contextlib import AbstractContextManager
from enum import Enum
from typing import Any

from ._core.callbacks import CallbackHandle
from ._core.errors import ExecError, WirelogInternError, WirelogModeError, check
from ._core.intern import InternTable
from ._ffi import LIB
from ._ffi import _advanced as _advanced_ffi  # noqa: F401  -- registers argtypes
from ._ffi import _easy as _easy_ffi  # noqa: F401  -- registers argtypes
from ._ffi._enums import BackendKind
from ._ffi._types import (
    EASY_OPEN_OPTS_SIZE,
    EasyOpenOptsStruct,
    EasySessionHandle,
    OnDeltaFn,
    SessionHandle,
)
from .program import Program

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


class Session(AbstractContextManager["Session"]):
    """Wrapper over the wirelog *advanced* session API (`wirelog_session_*`).

    The advanced API differs from `EasySession` in four ways:

    1. **Caller-owned program.** Pass a `Program` you created (and own).
       `Session` keeps a strong reference so the program stays alive
       while the session is open.
    2. **Backend selection.** Choose `BackendKind.DEFAULT` or
       `BackendKind.COLUMNAR` and a worker count at construction.
    3. **Batched insert / remove.** Pass a sequence of int64 rows in
       one FFI call.
    4. **No automatic string interning.** Callers either supply int64
       row values or pre-seed the intern table with `seed_intern`.

    Mode machine: the first `step()` or `set_delta_callback()` commits
    the session to INCREMENTAL mode; the first `snapshot()` commits it
    to QUERY mode. Crossing modes raises `WirelogModeError`.
    """

    def __init__(
        self,
        program: Program,
        *,
        backend: BackendKind = BackendKind.DEFAULT,
        num_workers: int = 0,
        lock: bool = True,
    ) -> None:
        self._program = program  # strong reference — program is borrowed
        self._handle: SessionHandle = SessionHandle()
        rc = LIB.wirelog_session_create(
            program._handle,
            ctypes.c_int(int(backend)),
            ctypes.c_uint32(int(num_workers)),
            ctypes.byref(self._handle),
        )
        check(rc)
        if not self._handle.value:
            raise ExecError("wirelog_session_create returned a NULL handle")

        self._lock: threading.RLock | None = threading.RLock() if lock else None
        self._closed: bool = False
        self._mode: _Mode = _Mode.UNSET
        self._delta_cb: CallbackHandle | None = None
        self._intern = InternTable(self._reject_intern)

    # --- intern ------------------------------------------------------------

    @staticmethod
    def _reject_intern(_b: bytes) -> int:
        raise WirelogInternError(
            "advanced Session has no public intern API; supply int64 values "
            "directly or call seed_intern(value, id) for known pairs"
        )

    def seed_intern(self, value: str, sym_id: int) -> None:
        """Pre-populate the (value, id) pair in the reverse-intern cache."""
        self._intern.remember(int(sym_id), value)

    @property
    def intern_table(self) -> InternTable:
        return self._intern

    # --- insert / remove ---------------------------------------------------

    def _flatten(self, rows: Sequence[Sequence[int]]) -> tuple[Any, int, int]:
        if not rows:
            return None, 0, 0
        ncols = len(rows[0])
        if ncols == 0:
            raise ValueError("rows must have at least one column")
        flat = (ctypes.c_int64 * (ncols * len(rows)))()
        for i, r in enumerate(rows):
            if len(r) != ncols:
                raise ValueError(f"row {i} has {len(r)} cols, expected {ncols} (first row)")
            for j, v in enumerate(r):
                flat[i * ncols + j] = int(v)
        return flat, len(rows), ncols

    def insert(self, relation: str, rows: Sequence[Sequence[int]]) -> None:
        """Batched insert. Every value must already be an `int64`."""
        self._require_mode(_Mode.INCREMENTAL)
        flat, nrows, ncols = self._flatten(rows)
        if not nrows:
            return
        with self._serialize():
            rc = LIB.wirelog_session_insert(
                self._handle,
                relation.encode("utf-8"),
                flat,
                ctypes.c_uint32(nrows),
                ctypes.c_uint32(ncols),
            )
        check(rc)

    def remove(self, relation: str, rows: Sequence[Sequence[int]]) -> None:
        """Batched retract (z-set multiplicity decrement by 1 per row)."""
        self._require_mode(_Mode.INCREMENTAL)
        flat, nrows, ncols = self._flatten(rows)
        if not nrows:
            return
        with self._serialize():
            rc = LIB.wirelog_session_remove(
                self._handle,
                relation.encode("utf-8"),
                flat,
                ctypes.c_uint32(nrows),
                ctypes.c_uint32(ncols),
            )
        check(rc)

    # --- step / snapshot / callbacks --------------------------------------

    def set_delta_callback(self, fn: Callable[[str, tuple[int, ...], int], None] | None) -> None:
        """Register or clear the delta callback. The session enters
        INCREMENTAL mode on the first call."""
        self._require_mode(_Mode.INCREMENTAL)
        if fn is None:
            if self._delta_cb is not None:
                with self._serialize():
                    rc = LIB.wirelog_session_set_delta_cb(self._handle, OnDeltaFn(), None)
                check(rc)
                self._delta_cb.close()
                self._delta_cb = None
            return
        if self._delta_cb is None:
            self._delta_cb = CallbackHandle("delta")
        self._delta_cb._state.user_fn = fn
        with self._serialize():
            rc = LIB.wirelog_session_set_delta_cb(
                self._handle, self._delta_cb.fn, self._delta_cb.user_data
            )
        check(rc)

    def step(self) -> list[tuple[str, tuple[int, ...], int]]:
        """Drive one fixpoint step. Returns `(relation, row, diff)` events
        that wirelog emitted for the delta callback during this step."""
        self._require_mode(_Mode.INCREMENTAL)
        if self._delta_cb is None:
            self._delta_cb = CallbackHandle("delta")
            with self._serialize():
                rc = LIB.wirelog_session_set_delta_cb(
                    self._handle, self._delta_cb.fn, self._delta_cb.user_data
                )
            check(rc)
        with self._serialize():
            rc = LIB.wirelog_session_step(self._handle)
        check(rc)
        events = self._delta_cb.drain()
        return [(rel, vals, diff) for _kind, rel, vals, diff in events]

    def snapshot(self) -> list[tuple[str, tuple[int, ...]]]:
        """Forward every IDB tuple. Returns `(relation, row)` pairs.

        Commits the session to QUERY mode; subsequent `step()` calls
        raise `WirelogModeError`.
        """
        self._require_mode(_Mode.QUERY)
        cb = CallbackHandle("tuple")
        try:
            with self._serialize():
                rc = LIB.wirelog_session_snapshot(self._handle, cb.fn, cb.user_data)
            check(rc)
            events = cb.drain()
        finally:
            cb.close()
        return [(rel, vals) for _kind, rel, vals in events]

    # --- lifecycle ---------------------------------------------------------

    @property
    def program(self) -> Program:
        return self._program

    def close(self) -> None:
        """Destroy the session. The borrowed `Program` is NOT freed —
        the caller still owns it."""
        if self._closed:
            return
        with self._lock if self._lock is not None else _NullCM():
            if self._delta_cb is not None:
                # Clear wirelog's pointer before tearing the slot down.
                try:
                    LIB.wirelog_session_set_delta_cb(self._handle, OnDeltaFn(), None)
                except Exception:
                    pass
                self._delta_cb.close()
                self._delta_cb = None
            if self._handle.value:
                LIB.wirelog_session_destroy(self._handle)
                self._handle = SessionHandle()
            self._closed = True

    def __exit__(self, *exc: object) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

    # --- internals ---------------------------------------------------------

    def _serialize(self) -> Any:
        return self._lock if self._lock is not None else _NullCM()

    def _require_mode(self, want: _Mode) -> None:
        if self._mode == _Mode.UNSET:
            self._mode = want
            return
        if self._mode != want:
            raise WirelogModeError(
                f"session is in {self._mode.name} mode; "
                f"{want.name} operation rejected. Close and reopen the "
                "session to switch modes."
            )


__all__ = ["EasySession", "Session"]
