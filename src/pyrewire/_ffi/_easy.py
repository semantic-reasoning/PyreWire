"""Raw ctypes bindings for `wirelog_easy_*` (the easy facade).

This module mirrors `wirelog/wirelog-easy.h` 1:1 — every function's
`argtypes`/`restype` lives here and nothing else. The high-level
`EasySession` class (M1, issue #9) builds on top.

Variadic helpers (`wirelog_easy_insert_sym`, `wirelog_easy_remove_sym`)
have only their `restype` set here. The variadic call surface is
finalized per-call by the `EasySession.insert_sym/remove_sym` wrappers
(issue #44) which save / restore `argtypes` under the session lock.
"""

from __future__ import annotations

import ctypes

from . import LIB
from ._types import (
    CompoundArgStruct,
    EasyOpenOptsStruct,
    EasySessionHandle,
    OnDeltaFn,
    OnTupleFn,
)


def _register() -> None:
    LIB.wirelog_easy_open.restype = ctypes.c_int
    LIB.wirelog_easy_open.argtypes = [
        ctypes.c_char_p,
        ctypes.POINTER(EasySessionHandle),
    ]

    LIB.wirelog_easy_open_opts.restype = ctypes.c_int
    LIB.wirelog_easy_open_opts.argtypes = [
        ctypes.c_char_p,
        ctypes.POINTER(EasyOpenOptsStruct),
        ctypes.POINTER(EasySessionHandle),
    ]

    LIB.wirelog_easy_close.restype = None
    LIB.wirelog_easy_close.argtypes = [EasySessionHandle]

    LIB.wirelog_easy_intern.restype = ctypes.c_int64
    LIB.wirelog_easy_intern.argtypes = [EasySessionHandle, ctypes.c_char_p]

    LIB.wirelog_easy_insert.restype = ctypes.c_int
    LIB.wirelog_easy_insert.argtypes = [
        EasySessionHandle,
        ctypes.c_char_p,
        ctypes.POINTER(ctypes.c_int64),
        ctypes.c_uint32,
    ]

    LIB.wirelog_easy_remove.restype = ctypes.c_int
    LIB.wirelog_easy_remove.argtypes = LIB.wirelog_easy_insert.argtypes

    # Variadic. argtypes left unset; high-level wrapper (#44) sets it
    # per call. restype must still be set so ctypes returns an int.
    LIB.wirelog_easy_insert_sym.restype = ctypes.c_int
    LIB.wirelog_easy_remove_sym.restype = ctypes.c_int

    LIB.wirelog_easy_step.restype = ctypes.c_int
    LIB.wirelog_easy_step.argtypes = [EasySessionHandle]

    LIB.wirelog_easy_snapshot.restype = ctypes.c_int
    LIB.wirelog_easy_snapshot.argtypes = [
        EasySessionHandle,
        ctypes.c_char_p,
        OnTupleFn,
        ctypes.c_void_p,
    ]

    LIB.wirelog_easy_set_delta_cb.restype = ctypes.c_int
    LIB.wirelog_easy_set_delta_cb.argtypes = [
        EasySessionHandle,
        OnDeltaFn,
        ctypes.c_void_p,
    ]

    LIB.wirelog_easy_make_compound.restype = ctypes.c_int
    LIB.wirelog_easy_make_compound.argtypes = [
        EasySessionHandle,
        ctypes.c_char_p,
        ctypes.c_uint32,
        ctypes.POINTER(CompoundArgStruct),
        ctypes.POINTER(ctypes.c_uint64),
    ]

    LIB.wirelog_easy_print_delta.restype = None
    LIB.wirelog_easy_print_delta.argtypes = [
        ctypes.c_char_p,
        ctypes.POINTER(ctypes.c_int64),
        ctypes.c_uint32,
        ctypes.c_int32,
        ctypes.c_void_p,
    ]

    LIB.wirelog_easy_banner.restype = None
    LIB.wirelog_easy_banner.argtypes = [ctypes.c_char_p]


_register()
