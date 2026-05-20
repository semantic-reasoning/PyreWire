"""Raw ctypes bindings for wirelog's IO-adapter ABI (#26).

Covers:

- `wirelog_io_register_adapter(adapter*) -> int`
- `wirelog_io_unregister_adapter(scheme) -> int`
- `wirelog_io_find_adapter(scheme) -> const wirelog_io_adapter_t *`
- `wirelog_io_last_error() -> const char *`
- `wirelog_io_ctx_relation_name(ctx) -> const char *`
- `wirelog_io_ctx_num_cols(ctx) -> uint32_t`
- `wirelog_io_ctx_col_type(ctx, col) -> wirelog_column_type_t`
- `wirelog_io_ctx_param(ctx, key) -> const char *`
- `wirelog_io_ctx_intern_string(ctx, utf8) -> int64_t`
- `wirelog_io_ctx_platform(ctx) -> void *`
- `wirelog_io_ctx_set_platform(ctx, ptr) -> int`

The high-level `@register_adapter` decorator (#27) builds on these.
"""

from __future__ import annotations

import ctypes

from . import LIB
from ._types import IOAdapterStruct, IOCtxHandle


def _register() -> None:
    LIB.wirelog_io_register_adapter.restype = ctypes.c_int
    LIB.wirelog_io_register_adapter.argtypes = [ctypes.POINTER(IOAdapterStruct)]

    LIB.wirelog_io_unregister_adapter.restype = ctypes.c_int
    LIB.wirelog_io_unregister_adapter.argtypes = [ctypes.c_char_p]

    LIB.wirelog_io_find_adapter.restype = ctypes.POINTER(IOAdapterStruct)
    LIB.wirelog_io_find_adapter.argtypes = [ctypes.c_char_p]

    LIB.wirelog_io_last_error.restype = ctypes.c_char_p
    LIB.wirelog_io_last_error.argtypes = []

    LIB.wirelog_io_ctx_relation_name.restype = ctypes.c_char_p
    LIB.wirelog_io_ctx_relation_name.argtypes = [IOCtxHandle]

    LIB.wirelog_io_ctx_num_cols.restype = ctypes.c_uint32
    LIB.wirelog_io_ctx_num_cols.argtypes = [IOCtxHandle]

    LIB.wirelog_io_ctx_col_type.restype = ctypes.c_int
    LIB.wirelog_io_ctx_col_type.argtypes = [IOCtxHandle, ctypes.c_uint32]

    LIB.wirelog_io_ctx_param.restype = ctypes.c_char_p
    LIB.wirelog_io_ctx_param.argtypes = [IOCtxHandle, ctypes.c_char_p]

    LIB.wirelog_io_ctx_intern_string.restype = ctypes.c_int64
    LIB.wirelog_io_ctx_intern_string.argtypes = [IOCtxHandle, ctypes.c_char_p]

    LIB.wirelog_io_ctx_platform.restype = ctypes.c_void_p
    LIB.wirelog_io_ctx_platform.argtypes = [IOCtxHandle]

    LIB.wirelog_io_ctx_set_platform.restype = ctypes.c_int
    LIB.wirelog_io_ctx_set_platform.argtypes = [IOCtxHandle, ctypes.c_void_p]


_register()
