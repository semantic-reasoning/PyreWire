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
from ._ffi._enums import BackendKind, ColumnType
from ._ffi._types import (
    EASY_OPEN_OPTS_SIZE,
    CompoundArgStruct,
    EasyOpenOptsStruct,
    EasySessionHandle,
    OnDeltaFn,
    SessionHandle,
)
from .compound import Compound, CompoundArg
from .program import Program, Schema

try:  # NumPy is an optional dependency for the zero-copy path (#22).
    import numpy as _np
except ImportError:  # pragma: no cover - exercised via monkeypatch
    _np = None  # type: ignore[assignment]

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


def _make_compound_call(
    fn: Any,
    handle: Any,
    functor: str,
    args: Sequence[CompoundArg],
    serialize_cm: Any,
) -> int:
    """Shared core of `make_compound` for both session classes.

    Builds the `wirelog_compound_arg_t[]` array, invokes `fn` under the
    given serialise context, and returns the raw `uint64_t` handle.
    Raises `WirelogError` (subclass) on a non-OK rc.
    """
    n = len(args)
    arr_t = CompoundArgStruct * max(n, 1)
    if n:
        arr = arr_t(*(a.to_struct() for a in args))
    else:
        arr = arr_t()
    out = ctypes.c_uint64(0)
    with serialize_cm:
        rc = fn(
            handle,
            functor.encode("utf-8"),
            ctypes.c_uint32(n),
            arr,
            ctypes.byref(out),
        )
    check(rc)
    if out.value == 0:
        raise ExecError(f"make_compound returned NULL handle for {functor}/{n}")
    return int(out.value)


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
        self._compounds: list[Compound] = []

        # Optional side-program for Python-level introspection (#47):
        # parses the same source again so callers can ask for schemas
        # and inline facts without crossing the wirelog easy handle.
        # If a re-parse fails (e.g. wirelog's parser disagrees with
        # the easy facade about what is well-formed) we keep `None` so
        # `preview_inline_facts` falls back to an empty list rather
        # than aborting the session.
        try:
            self._schema_program: Program | None = Program.from_string(dl_src)
        except Exception:
            self._schema_program = None
        # Per-relation Schema cache (#43). Populated lazily by
        # `_schema_for(rel)`; `step()` / `snapshot()` decode rows
        # through this cache so the wirelog program is only consulted
        # once per relation.
        self._schema_cache: dict[str, Schema] = {}
        # Delta-mode callback handle (#10). Created lazily on the
        # first `set_delta_callback` / `step` call.
        self._delta_cb: CallbackHandle | None = None

    # --- intern -------------------------------------------------------------

    def _intern_raw(self, symbol_bytes: bytes) -> int:
        return int(LIB.wirelog_easy_intern(self._handle, symbol_bytes))

    def intern(self, value: str) -> int:
        """Return the id wirelog assigns to `value`. Cached after the
        first call for the same string."""
        with self._serialize():
            return self._intern.intern(value)

    # --- schema cache (#43) ------------------------------------------------

    def _schema_for(self, relation: str) -> Schema:
        """Return the relation's `Schema`, cached after the first lookup.

        Used by the forthcoming `step()` / `snapshot()` (and the existing
        `_decode_row` helper in the advanced `Session`) to turn raw
        `int64` rows back into typed Python values.

        Raises `ExecError` if the relation is not declared in the
        owned program, or if the helper Program could not be built at
        session open time.
        """
        cached = self._schema_cache.get(relation)
        if cached is not None:
            return cached
        if self._schema_program is None:
            raise ExecError(f"schema cache is closed; cannot decode relation {relation!r}")
        sch = self._schema_program.schema(relation)
        if sch is None:
            raise ExecError(f"no schema for relation: {relation!r}")
        self._schema_cache[relation] = sch
        return sch

    # --- inline-fact preview (#47) -----------------------------------------

    def preview_inline_facts(self, relation: str) -> list[tuple[object, ...]]:
        """Return rows already present in `relation` from inline `.dl`
        facts at session open time.

        Use this to dedupe against the EDB before calling `insert()`:

            already = set(s.preview_inline_facts("friend"))
            for row in incoming:
                if tuple(row) not in already:
                    s.insert("friend", row)

        Otherwise, reinserting an inline fact raises the row's z-set
        multiplicity to +2; a single `remove()` will not retract it.

        Returns an empty list if the side-program parse failed at
        construction (i.e. PyreWire could not build a Python-side view
        of the program).
        """
        if self._schema_program is None:
            return []
        try:
            return self._schema_program.facts(relation, intern=self._intern)
        except ExecError:
            return []

    def insert_with_dedupe(self, relation: str, row: Row) -> bool:
        """Insert `row` only if it is not already in `relation` from
        inline facts. Returns True if a new row was inserted, False if
        it was a duplicate that was skipped."""
        existing = {tuple(r) for r in self.preview_inline_facts(relation)}
        if tuple(row) in existing:
            return False
        self.insert(relation, row)
        return True

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

    # --- variadic *_sym wrappers (#44) -------------------------------------
    #
    # `wirelog_easy_insert_sym` / `remove_sym` are variadic in C: a fixed
    # `(session, relation)` prefix, then up to 16 `const char *` symbols,
    # then a NULL sentinel. On Apple Silicon (macOS arm64) variadic
    # functions use a different ABI than fixed-arity functions, and
    # ctypes needs `argtypes` to describe *only* the fixed arguments —
    # the variadic tail uses the platform's variadic ABI from there.
    # See https://docs.python.org/3/library/ctypes.html#calling-variadic-functions
    #
    # On non-Apple-arm64 platforms this still works because ctypes uses
    # the fixed signature for the leading args and the platform's
    # default convention for the rest.

    _SYM_MAX = 16
    _SYM_FIXED_ARGTYPES = (EasySessionHandle, ctypes.c_char_p)

    # --- step / set_delta_callback / snapshot (#10 + #11) ----------------

    def set_delta_callback(
        self,
        fn: Callable[[tuple[str, tuple[object, ...], int]], None] | None,
    ) -> None:
        """Register (or clear) a user callable invoked once per delta
        produced by `step()`. Commits the session to INCREMENTAL mode.

        Rejects `wirelog_easy_print_delta` (and other ctypes function
        pointers that alias it) — the C function aborts the process on
        a missing reverse-intern. Use
        :func:`pyrewire.helpers.make_safe_print_delta` instead.
        """
        if fn is not None:
            from .helpers import is_wirelog_print_delta

            if is_wirelog_print_delta(fn):
                raise TypeError(
                    "Refusing to register wirelog_easy_print_delta as a "
                    "Python delta callback: it calls abort() on a missing "
                    "reverse-intern. Use "
                    "pyrewire.helpers.make_safe_print_delta(session._intern) "
                    "instead."
                )
        self._require_mode(_Mode.INCREMENTAL)
        if fn is None:
            if self._delta_cb is not None:
                with self._serialize():
                    rc = LIB.wirelog_easy_set_delta_cb(self._handle, OnDeltaFn(), None)
                check(rc)
                self._delta_cb.close()
                self._delta_cb = None
            return
        if self._delta_cb is None:
            self._delta_cb = CallbackHandle("delta")
        self._delta_cb._state.user_fn = fn
        with self._serialize():
            rc = LIB.wirelog_easy_set_delta_cb(
                self._handle, self._delta_cb.fn, self._delta_cb.user_data
            )
        check(rc)

    def step(self) -> list[tuple[str, tuple[object, ...], int]]:
        """Drive one fixpoint step. Returns decoded delta events with
        `STRING` columns reverse-interned through the session's
        `InternTable` and numeric/bool/float columns decoded by the
        per-relation schema cache. Commits the session to INCREMENTAL
        mode."""
        self._require_mode(_Mode.INCREMENTAL)
        if self._delta_cb is None:
            self._delta_cb = CallbackHandle("delta")
            with self._serialize():
                rc = LIB.wirelog_easy_set_delta_cb(
                    self._handle, self._delta_cb.fn, self._delta_cb.user_data
                )
            check(rc)
        with self._serialize():
            rc = LIB.wirelog_easy_step(self._handle)
        check(rc)
        events = self._delta_cb.drain()
        decoded: list[tuple[str, tuple[object, ...], int]] = []
        for _kind, rel, ids, diff in events:
            decoded.append((rel, self._decode_row(rel, ids), int(diff)))
        user_fn = self._delta_cb._state.user_fn
        if user_fn is not None:
            for ev in decoded:
                user_fn(ev)
        return decoded

    def snapshot(self, relation: str) -> list[tuple[object, ...]]:
        """Forward every IDB tuple of `relation` via a one-shot
        callback. Commits the session to QUERY mode."""
        self._require_mode(_Mode.QUERY)
        cb = CallbackHandle("tuple")
        try:
            with self._serialize():
                rc = LIB.wirelog_easy_snapshot(
                    self._handle,
                    relation.encode("utf-8"),
                    cb.fn,
                    cb.user_data,
                )
            check(rc)
            events = cb.drain()
        finally:
            cb.close()
        return [self._decode_row(rel, ids) for _kind, rel, ids in events]

    def _decode_row(self, relation: str, ids: tuple[int, ...]) -> tuple[object, ...]:
        """Map an int64 row back to typed Python values via the schema
        cache and the session's InternTable."""
        try:
            sch = self._schema_for(relation)
        except ExecError:
            # Unknown relation — surface raw ids rather than crashing.
            return tuple(int(v) for v in ids)
        out: list[object] = []
        ncols = min(len(sch.columns), len(ids))
        for i in range(ncols):
            col = sch.columns[i]
            raw = ids[i]
            if col.type == ColumnType.STRING:
                try:
                    out.append(self._intern.lookup(int(raw)))
                except Exception:
                    out.append(int(raw))
            elif col.type == ColumnType.BOOL:
                out.append(bool(raw))
            elif col.type == ColumnType.FLOAT:
                out.append(ctypes.c_double.from_buffer_copy(ctypes.c_int64(raw)).value)
            else:
                out.append(int(raw))
        for j in range(ncols, len(ids)):
            out.append(int(ids[j]))
        return tuple(out)

    def insert_sym(self, relation: str, *symbols: str) -> None:
        """Insert one row by listing its `STRING` symbols inline.

        Equivalent to `insert(relation, list(symbols))` but routed
        through `wirelog_easy_insert_sym` for ABI parity with the C
        surface. Symbols are interned by wirelog; PyreWire mirrors
        them into its reverse-intern cache after the call succeeds.

        Caps at 16 symbols per call (wirelog header constraint).
        """
        self._sym_call(LIB.wirelog_easy_insert_sym, relation, symbols)

    def remove_sym(self, relation: str, *symbols: str) -> None:
        """Retract one row by inline symbols (z-set decrement)."""
        self._sym_call(LIB.wirelog_easy_remove_sym, relation, symbols)

    def _sym_call(self, fn: Any, relation: str, symbols: tuple[str, ...]) -> None:
        self._require_mode(_Mode.INCREMENTAL)
        if len(symbols) > self._SYM_MAX:
            raise ValueError(
                f"wirelog_easy_{{insert,remove}}_sym accepts at most "
                f"{self._SYM_MAX} symbols per call (got {len(symbols)})"
            )
        # Set argtypes for the FIXED arguments only; ctypes uses the
        # platform's variadic ABI for the remaining `const char *`
        # symbols + NULL terminator. Pre-wrap each variadic arg in
        # `c_char_p` so the default ctypes coercion is bypassed.
        prev_argtypes = fn.argtypes
        try:
            with self._serialize():
                fn.argtypes = list(self._SYM_FIXED_ARGTYPES)
                args: list[Any] = [self._handle, relation.encode("utf-8")]
                args.extend(ctypes.c_char_p(s.encode("utf-8")) for s in symbols)
                args.append(ctypes.c_char_p(None))  # NULL terminator
                rc = fn(*args)
        finally:
            fn.argtypes = prev_argtypes
        check(rc)
        for s in symbols:
            self._intern.intern(s)

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

    # --- compounds ----------------------------------------------------------

    def make_compound(self, functor: str, args: Sequence[CompoundArg]) -> Compound:
        """Allocate a session-local compound. The returned `Compound`
        becomes invalid when this session is closed."""
        h = _make_compound_call(
            LIB.wirelog_easy_make_compound,
            self._handle,
            functor,
            args,
            self._serialize(),
        )
        c = Compound(self, functor, len(args), h)
        self._compounds.append(c)
        return c

    # --- lifecycle ----------------------------------------------------------

    def close(self) -> None:
        """Idempotently free the underlying wirelog handle."""
        if self._closed:
            return
        with self._lock if self._lock is not None else _NullCM():
            for c in self._compounds:
                c.invalidate()
            self._compounds.clear()
            if self._schema_program is not None:
                self._schema_program.close()
                self._schema_program = None
            self._schema_cache.clear()
            if self._delta_cb is not None:
                # Best-effort clear before tearing down the slot;
                # wirelog may have already invalidated the pointer.
                try:
                    LIB.wirelog_easy_set_delta_cb(self._handle, OnDeltaFn(), None)
                except Exception:
                    pass
                self._delta_cb.close()
                self._delta_cb = None
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
        self._compounds: list[Compound] = []

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

    # --- inline-fact preview (#47) -----------------------------------------

    def preview_inline_facts(self, relation: str) -> list[tuple[object, ...]]:
        """Return rows already present in `relation` from inline `.dl`
        facts in the borrowed program.

        STRING columns are reverse-interned through this session's
        `InternTable`. Because the advanced session has no public
        forward-intern entry point, callers that want decoded strings
        should `seed_intern(value, id)` for every known pair before
        calling this method.

        Returns an empty list if the relation is unknown to the program.
        """
        try:
            return self._program.facts(relation, intern=self._intern)
        except ExecError:
            return []

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

    # --- zero-copy NumPy path (#22) ----------------------------------------

    def insert_batch(self, relation: str, rows: Any) -> None:
        """Batched insert that accepts a 2-D `int64` NumPy array (or any
        2-D sequence of ints). When the input is an ndarray that is
        already `int64` and C-contiguous, wirelog reads the buffer
        directly without copying.
        """
        self._require_mode(_Mode.INCREMENTAL)
        self._batch_iud(relation, rows, LIB.wirelog_session_insert)

    def remove_batch(self, relation: str, rows: Any) -> None:
        """Like `insert_batch` but emits z-set decrements."""
        self._require_mode(_Mode.INCREMENTAL)
        self._batch_iud(relation, rows, LIB.wirelog_session_remove)

    def _batch_iud(self, relation: str, rows: Any, fn: Any) -> None:
        if _np is not None and isinstance(rows, _np.ndarray):
            arr = rows
            if arr.ndim != 2:
                raise ValueError(f"rows ndarray must be 2-D, got ndim={arr.ndim}")
            if arr.dtype != _np.int64:
                arr = arr.astype(_np.int64, copy=False)
            if not arr.flags["C_CONTIGUOUS"]:
                arr = _np.ascontiguousarray(arr)
            nrows, ncols = arr.shape
            if nrows == 0:
                return
            buf = arr.ctypes.data_as(ctypes.POINTER(ctypes.c_int64))
            with self._serialize():
                rc = fn(
                    self._handle,
                    relation.encode("utf-8"),
                    buf,
                    ctypes.c_uint32(nrows),
                    ctypes.c_uint32(ncols),
                )
            check(rc)
            # Keep `arr` alive until after the FFI call returns. It is
            # local to this function, so this is implicit, but make the
            # invariant explicit for readers.
            del arr
            return
        # Fallback: list-of-lists path through the existing flattener.
        flat, nrows, ncols = self._flatten(rows)
        if not nrows:
            return
        with self._serialize():
            rc = fn(
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

    # --- compounds ---------------------------------------------------------

    def make_compound(self, functor: str, args: Sequence[CompoundArg]) -> Compound:
        """Allocate a session-local compound. The returned `Compound`
        becomes invalid when this session is closed."""
        h = _make_compound_call(
            LIB.wirelog_session_make_compound,
            self._handle,
            functor,
            args,
            self._serialize(),
        )
        c = Compound(self, functor, len(args), h)
        self._compounds.append(c)
        return c

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
            for c in self._compounds:
                c.invalidate()
            self._compounds.clear()
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
