# SPDX-License-Identifier: Apache-2.0 OR GPL-3.0-or-later
"""Raw ctypes bindings for the wirelog advanced session API (#20).

Covers 12 entry points from `wirelog/wirelog-advanced.h`:

- `wirelog_session_create(program, backend, num_workers, &out) -> wirelog_error_t`
- `wirelog_session_destroy(session) -> void`
- `wirelog_session_insert(session, rel, data, num_rows, num_cols) -> wirelog_error_t`
- `wirelog_session_remove(session, rel, data, num_rows, num_cols) -> wirelog_error_t`
- `wirelog_session_step(session) -> wirelog_error_t`
- `wirelog_session_snapshot(session, cb, user_data) -> wirelog_error_t`
- `wirelog_session_set_delta_cb(session, cb, user_data) -> wirelog_error_t`
- `wirelog_session_make_compound(session, functor, arity, args, &handle_out) -> wirelog_error_t`
- `wirelog_session_insert_typed(session, rel, rows, num_rows, &err) -> wirelog_error_t`
- `wirelog_session_remove_typed(session, rel, rows, num_rows, &err) -> wirelog_error_t`
- `wirelog_session_snapshot_typed(session, cb, user_data) -> wirelog_error_t`
- `wirelog_session_set_typed_delta_cb(session, cb, user_data) -> wirelog_error_t`

The advanced session BORROWS its `wirelog_program_t`; the high-level
`Session` class (#21) is responsible for keeping the program alive
for the lifetime of the session.

`insert` / `remove` take BATCHED rows (`num_rows * num_cols`),
unlike the easy facade which takes one row per call. This is the
documented advanced-API shape.

The four `*_typed` entry points are the only way a FLOAT column
crosses the FFI boundary with its value intact. The untyped entry
points carry `int64_t` lanes, and on a relation that declares a FLOAT
column wirelog refuses them outright rather than distorting the value.
The typed descriptors are borrowed for the duration of the call and
never retained.
"""

from __future__ import annotations

import ctypes

from . import LIB
from ._types import (
    CompoundArgStruct,
    OnDeltaFn,
    OnTupleFn,
    OnTypedTupleFn,
    ProgramHandle,
    SessionHandle,
    TypedErrorStruct,
    TypedRowStruct,
)

TYPED_ROW_ENTRY_POINTS = (
    "wirelog_session_insert_typed",
    "wirelog_session_remove_typed",
    "wirelog_session_snapshot_typed",
    "wirelog_session_set_typed_delta_cb",
)


def has_typed_row_api() -> bool:
    """Whether the loaded libwirelog exports the typed row entry points.

    False on any engine older than 0.60.0. Callers should raise
    `WirelogVersionError` rather than let ctypes fail with a bare
    `AttributeError`.
    """
    return all(hasattr(LIB, name) for name in TYPED_ROW_ENTRY_POINTS)


def _register() -> None:
    LIB.wirelog_session_create.restype = ctypes.c_int
    LIB.wirelog_session_create.argtypes = [
        ProgramHandle,
        ctypes.c_int,  # wirelog_backend_kind_t
        ctypes.c_uint32,
        ctypes.POINTER(SessionHandle),
    ]

    LIB.wirelog_session_destroy.restype = None
    LIB.wirelog_session_destroy.argtypes = [SessionHandle]

    LIB.wirelog_session_insert.restype = ctypes.c_int
    LIB.wirelog_session_insert.argtypes = [
        SessionHandle,
        ctypes.c_char_p,
        ctypes.POINTER(ctypes.c_int64),
        ctypes.c_uint32,
        ctypes.c_uint32,
    ]

    LIB.wirelog_session_remove.restype = ctypes.c_int
    LIB.wirelog_session_remove.argtypes = LIB.wirelog_session_insert.argtypes

    LIB.wirelog_session_step.restype = ctypes.c_int
    LIB.wirelog_session_step.argtypes = [SessionHandle]

    LIB.wirelog_session_snapshot.restype = ctypes.c_int
    LIB.wirelog_session_snapshot.argtypes = [
        SessionHandle,
        OnTupleFn,
        ctypes.c_void_p,
    ]

    LIB.wirelog_session_set_delta_cb.restype = ctypes.c_int
    LIB.wirelog_session_set_delta_cb.argtypes = [
        SessionHandle,
        OnDeltaFn,
        ctypes.c_void_p,
    ]

    LIB.wirelog_session_make_compound.restype = ctypes.c_int
    LIB.wirelog_session_make_compound.argtypes = [
        SessionHandle,
        ctypes.c_char_p,
        ctypes.c_uint32,
        ctypes.POINTER(CompoundArgStruct),
        ctypes.POINTER(ctypes.c_uint64),
    ]

    # The typed row entry points first ship in wirelog 0.60.0, while the
    # loader floor still admits 0.52.0. Register them guardedly, the same
    # way `_parser` handles `wirelog_program_get_relation_ir`: an
    # unguarded attribute access here would raise AttributeError at import
    # time and take the whole package down on an older engine.
    if has_typed_row_api():
        LIB.wirelog_session_insert_typed.restype = ctypes.c_int
        LIB.wirelog_session_insert_typed.argtypes = [
            SessionHandle,
            ctypes.c_char_p,
            ctypes.POINTER(TypedRowStruct),
            ctypes.c_uint32,
            ctypes.POINTER(TypedErrorStruct),
        ]

        LIB.wirelog_session_remove_typed.restype = ctypes.c_int
        # `list(...)`: sharing one mutable list between two ctypes
        # function objects would let a later in-place edit retype both.
        LIB.wirelog_session_remove_typed.argtypes = list(LIB.wirelog_session_insert_typed.argtypes)

        LIB.wirelog_session_snapshot_typed.restype = ctypes.c_int
        LIB.wirelog_session_snapshot_typed.argtypes = [
            SessionHandle,
            OnTypedTupleFn,
            ctypes.c_void_p,
        ]

        LIB.wirelog_session_set_typed_delta_cb.restype = ctypes.c_int
        LIB.wirelog_session_set_typed_delta_cb.argtypes = list(
            LIB.wirelog_session_snapshot_typed.argtypes
        )


_register()
