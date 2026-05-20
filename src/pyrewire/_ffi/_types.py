"""ctypes structures and callback function-pointer types mirroring
wirelog's public C ABI.

Opaque handles are aliased as `ctypes.c_void_p` because their underlying
struct layouts are intentionally hidden by wirelog. The two callback
types (`OnTupleFn`, `OnDeltaFn`) are module-level CFUNCTYPE definitions
so trampoline instances created from them remain stable singletons.
"""
from __future__ import annotations

import ctypes

# --- Opaque handles (treated as void * on the wire) -------------------------
ProgramHandle = ctypes.c_void_p
ExecutorHandle = ctypes.c_void_p
ResultHandle = ctypes.c_void_p
SessionHandle = ctypes.c_void_p
EasySessionHandle = ctypes.c_void_p
InternHandle = ctypes.c_void_p
IRNodeHandle = ctypes.c_void_p
IOCtxHandle = ctypes.c_void_p

# `WIRELOG_COMPOUND_HANDLE_NULL == 0`
CompoundHandleT = ctypes.c_uint64


# --- wirelog_parse_error_t --------------------------------------------------
class ParseErrorStruct(ctypes.Structure):
    """Mirrors `wirelog_parse_error_t` from wirelog-parser.h."""

    _fields_ = [
        ("error_code", ctypes.c_int),    # wirelog_error_t
        ("message", ctypes.c_char_p),
        ("line", ctypes.c_uint32),
        ("column", ctypes.c_uint32),
        ("source", ctypes.c_char_p),
    ]


# --- wirelog_column_t -------------------------------------------------------
class ColumnStruct(ctypes.Structure):
    """Mirrors `wirelog_column_t` from wirelog-types.h."""

    _fields_ = [
        ("name", ctypes.c_char_p),
        ("type", ctypes.c_int),                          # ColumnType
        ("compound_kind", ctypes.c_int),                 # CompoundKind
        ("compound_functor_id", ctypes.c_uint32),
        ("compound_arity", ctypes.c_uint32),
        ("compound_inline_col_offset", ctypes.c_uint32),
    ]


# --- wirelog_schema_t -------------------------------------------------------
class SchemaStruct(ctypes.Structure):
    """Mirrors `wirelog_schema_t`."""

    _fields_ = [
        ("relation_name", ctypes.c_char_p),
        ("columns", ctypes.POINTER(ColumnStruct)),
        ("column_count", ctypes.c_uint32),
    ]


# --- wirelog_stratum_t ------------------------------------------------------
class StratumStruct(ctypes.Structure):
    """Mirrors `wirelog_stratum_t`."""

    _fields_ = [
        ("stratum_id", ctypes.c_uint32),
        ("rule_names", ctypes.POINTER(ctypes.c_char_p)),
        ("rule_count", ctypes.c_uint32),
        ("is_recursive", ctypes.c_bool),
    ]


# --- wirelog_compound_arg_t -------------------------------------------------
class CompoundArgStruct(ctypes.Structure):
    """Mirrors `wirelog_compound_arg_t`."""

    _fields_ = [
        ("type", ctypes.c_int),       # ColumnType
        ("value", ctypes.c_int64),
    ]


# --- wirelog_easy_open_opts_t -----------------------------------------------
class EasyOpenOptsStruct(ctypes.Structure):
    """Mirrors `wirelog_easy_open_opts_t`. `size` MUST be set to
    `EASY_OPEN_OPTS_SIZE` so the C side accepts the struct."""

    _fields_ = [
        ("size", ctypes.c_uint32),
        ("num_workers", ctypes.c_uint32),
        ("eager_build", ctypes.c_bool),
        ("_reserved", ctypes.c_void_p),
    ]


EASY_OPEN_OPTS_SIZE = ctypes.sizeof(EasyOpenOptsStruct)


# --- Callback function-pointer types ---------------------------------------
#
# Module-level CFUNCTYPE definitions so trampoline instances are stable
# singletons. Defining them inside functions would create a fresh type per
# call and break wirelog's pointer-equality identification of the callback.

OnTupleFn = ctypes.CFUNCTYPE(
    None,                       # void return
    ctypes.c_char_p,            # const char *relation
    ctypes.POINTER(ctypes.c_int64),  # const int64_t *row
    ctypes.c_uint32,            # uint32_t ncols
    ctypes.c_void_p,            # void *user_data
)

OnDeltaFn = ctypes.CFUNCTYPE(
    None,
    ctypes.c_char_p,
    ctypes.POINTER(ctypes.c_int64),
    ctypes.c_uint32,
    ctypes.c_int32,             # int32_t diff (+1 / -1)
    ctypes.c_void_p,
)


# --- wirelog_io_adapter_t (ABI version 2) ----------------------------------
#
# The adapter struct stores function pointers using a fixed CFUNCTYPE
# signature documented in `wirelog/io/io_adapter.h`. The struct must remain
# alive for the lifetime of the registration; see `pyrewire.io_adapter` (M6)
# for the keep-alive registry that owns instances of this struct.

_IOReadFn = ctypes.CFUNCTYPE(
    ctypes.c_int,
    IOCtxHandle,
    ctypes.POINTER(ctypes.POINTER(ctypes.c_int64)),
    ctypes.POINTER(ctypes.c_uint32),
    ctypes.c_void_p,
)

_IOValidateFn = ctypes.CFUNCTYPE(
    ctypes.c_int,
    IOCtxHandle,
    ctypes.c_char_p,
    ctypes.c_size_t,
    ctypes.c_void_p,
)


class IOAdapterStruct(ctypes.Structure):
    """Mirrors `wirelog_io_adapter_t` from io/io_adapter.h."""

    _fields_ = [
        ("abi_version", ctypes.c_uint32),
        ("scheme", ctypes.c_char_p),
        ("description", ctypes.c_char_p),
        ("read", _IOReadFn),
        ("validate", _IOValidateFn),
        ("user_data", ctypes.c_void_p),
    ]


WIRELOG_IO_ABI_VERSION = 2


__all__ = [
    # Handles
    "ProgramHandle",
    "ExecutorHandle",
    "ResultHandle",
    "SessionHandle",
    "EasySessionHandle",
    "InternHandle",
    "IRNodeHandle",
    "IOCtxHandle",
    "CompoundHandleT",
    # Structs
    "ParseErrorStruct",
    "ColumnStruct",
    "SchemaStruct",
    "StratumStruct",
    "CompoundArgStruct",
    "EasyOpenOptsStruct",
    "IOAdapterStruct",
    # Constants
    "EASY_OPEN_OPTS_SIZE",
    "WIRELOG_IO_ABI_VERSION",
    # Callback types
    "OnTupleFn",
    "OnDeltaFn",
]
