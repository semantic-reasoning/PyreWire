"""Enums mirroring wirelog public C enums.

Values match `wirelog/wirelog.h` and `wirelog/wirelog-types.h` byte-for-byte.
Membership names drop the `WIRELOG_` prefix to read naturally on the Python
side (e.g. `ColumnType.INT32` mirrors `WIRELOG_TYPE_INT32`).
"""

from __future__ import annotations

from enum import IntEnum


class ErrorCode(IntEnum):
    """Mirrors `wirelog_error_t` from wirelog.h."""

    OK = 0
    PARSE = 1
    INVALID_IR = 2
    EXEC = 3
    MEMORY = 4
    IO = 5
    COMPOUND_SATURATED = 6
    COMPOUND_BUSY = 7
    UNKNOWN = 255


class ColumnType(IntEnum):
    """Mirrors `wirelog_column_type_t`."""

    INT32 = 0
    INT64 = 1
    UINT32 = 2
    UINT64 = 3
    FLOAT = 4
    STRING = 5
    BOOL = 6


class CompoundKind(IntEnum):
    """Mirrors `wirelog_compound_kind_t`."""

    NONE = 0
    INLINE = 1
    SIDE = 2


class CmpOp(IntEnum):
    """Mirrors `wirelog_cmp_op_t`."""

    EQ = 0
    NEQ = 1
    LT = 2
    GT = 3
    LTE = 4
    GTE = 5


class ArithOp(IntEnum):
    """Mirrors `wirelog_arith_op_t`."""

    ADD = 0
    SUB = 1
    MUL = 2
    DIV = 3
    MOD = 4
    BAND = 5
    BOR = 6
    BXOR = 7
    BNOT = 8
    SHL = 9
    SHR = 10
    HASH = 11
    CRC32_ETH = 12
    CRC32_CAST = 13
    MD5 = 14
    SHA1 = 15
    SHA256 = 16
    SHA512 = 17
    HMAC_SHA256 = 18
    UUID4 = 19
    UUID5 = 20


class AggFn(IntEnum):
    """Mirrors `wirelog_agg_fn_t`."""

    COUNT = 0
    SUM = 1
    MIN = 2
    MAX = 3
    AVG = 4


class StrFn(IntEnum):
    """Mirrors `wirelog_str_fn_t`."""

    STRLEN = 0
    CAT = 1
    SUBSTR = 2
    CONTAINS = 3
    STR_PREFIX = 4
    STR_SUFFIX = 5
    STR_ORD = 6
    TO_UPPER = 7
    TO_LOWER = 8
    STR_REPLACE = 9
    TRIM = 10
    TO_STRING = 11
    TO_NUMBER = 12


class BackendKind(IntEnum):
    """Mirrors `wirelog_backend_kind_t` from wirelog-advanced.h."""

    DEFAULT = 0
    COLUMNAR = 1


class IRNodeType(IntEnum):
    """Mirrors `wirelog_ir_node_type_t` from wirelog-ir.h."""

    SCAN = 0
    PROJECT = 1
    FILTER = 2
    JOIN = 3
    FLATMAP = 4
    AGGREGATE = 5
    ANTIJOIN = 6
    UNION = 7
    SEMIJOIN = 8
    COMPOUND_INLINE = 9
    COMPOUND_SIDE = 10


__all__ = [
    "ErrorCode",
    "ColumnType",
    "CompoundKind",
    "CmpOp",
    "ArithOp",
    "AggFn",
    "StrFn",
    "BackendKind",
    "IRNodeType",
]
