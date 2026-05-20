"""Raw ctypes bindings for the wirelog advanced session API (#20).

Covers 8 entry points from `wirelog/wirelog-advanced.h`:

- `wirelog_session_create(program, backend, num_workers, &out) -> wirelog_error_t`
- `wirelog_session_destroy(session) -> void`
- `wirelog_session_insert(session, rel, data, num_rows, num_cols) -> wirelog_error_t`
- `wirelog_session_remove(session, rel, data, num_rows, num_cols) -> wirelog_error_t`
- `wirelog_session_step(session) -> wirelog_error_t`
- `wirelog_session_snapshot(session, cb, user_data) -> wirelog_error_t`
- `wirelog_session_set_delta_cb(session, cb, user_data) -> wirelog_error_t`
- `wirelog_session_make_compound(session, functor, arity, args, &handle_out) -> wirelog_error_t`

The advanced session BORROWS its `wirelog_program_t`; the high-level
`Session` class (#21) is responsible for keeping the program alive
for the lifetime of the session.

`insert` / `remove` take BATCHED rows (`num_rows * num_cols`),
unlike the easy facade which takes one row per call. This is the
documented advanced-API shape.
"""

from __future__ import annotations

import ctypes

from . import LIB
from ._types import (
    CompoundArgStruct,
    OnDeltaFn,
    OnTupleFn,
    ProgramHandle,
    SessionHandle,
)


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


_register()
