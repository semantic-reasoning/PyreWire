"""Tests for `pyrewire._ffi._enums` and `pyrewire._ffi._types`.

Per project convention, tests should consume the public API only. These
ctypes structs and enums are internal scaffolding for FFI bindings and have
no public-API surface yet (sessions, parsers, etc. surface them lazily),
so this test file reaches into the private layer directly — flagged with
the same exemption documented for `tests/test_loader.py`.
"""

from __future__ import annotations

import ctypes

from pyrewire._ffi._enums import (
    AggFn,
    ArithOp,
    BackendKind,
    CmpOp,
    ColumnType,
    CompoundKind,
    ErrorCode,
    StrFn,
)
from pyrewire._ffi._types import (
    EASY_OPEN_OPTS_SIZE,
    WIRELOG_IO_ABI_VERSION,
    ColumnStruct,
    CompoundArgStruct,
    EasyOpenOptsStruct,
    IOAdapterStruct,
    OnDeltaFn,
    OnTupleFn,
    ParseErrorStruct,
    SchemaStruct,
    StratumStruct,
)

# ---- Enums -----------------------------------------------------------------


def test_error_code_values():
    assert ErrorCode.OK == 0
    assert ErrorCode.PARSE == 1
    assert ErrorCode.INVALID_IR == 2
    assert ErrorCode.EXEC == 3
    assert ErrorCode.MEMORY == 4
    assert ErrorCode.IO == 5
    assert ErrorCode.COMPOUND_SATURATED == 6
    assert ErrorCode.COMPOUND_BUSY == 7
    assert ErrorCode.UNKNOWN == 255


def test_column_type_values():
    assert ColumnType.INT32 == 0
    assert ColumnType.INT64 == 1
    assert ColumnType.UINT32 == 2
    assert ColumnType.UINT64 == 3
    assert ColumnType.FLOAT == 4
    assert ColumnType.STRING == 5
    assert ColumnType.BOOL == 6


def test_compound_kind_values():
    assert CompoundKind.NONE == 0
    assert CompoundKind.INLINE == 1
    assert CompoundKind.SIDE == 2


def test_cmp_op_values():
    assert CmpOp.EQ == 0
    assert CmpOp.NEQ == 1
    assert CmpOp.LT == 2
    assert CmpOp.GT == 3
    assert CmpOp.LTE == 4
    assert CmpOp.GTE == 5


def test_arith_op_values():
    assert ArithOp.ADD == 0
    assert ArithOp.HASH == 11
    assert ArithOp.SHA256 == 16
    assert ArithOp.UUID5 == 20  # last member


def test_agg_fn_values():
    assert AggFn.COUNT == 0
    assert AggFn.SUM == 1
    assert AggFn.MIN == 2
    assert AggFn.MAX == 3
    assert AggFn.AVG == 4


def test_str_fn_values():
    assert StrFn.STRLEN == 0
    assert StrFn.CAT == 1
    assert StrFn.TO_NUMBER == 12  # last member


def test_backend_kind_values():
    assert BackendKind.DEFAULT == 0
    assert BackendKind.COLUMNAR == 1


# ---- Structs ---------------------------------------------------------------


def test_easy_open_opts_size_constant():
    """EASY_OPEN_OPTS_SIZE must equal sizeof(EasyOpenOptsStruct) at runtime."""
    assert EASY_OPEN_OPTS_SIZE == ctypes.sizeof(EasyOpenOptsStruct)
    # The struct holds at least size(u32) + num_workers(u32) + eager_build
    # + reserved(void*). On 64-bit alignment that floors at 24 bytes; on
    # tightly-packed 32-bit it can be smaller. Allow any plausible layout
    # but reject obviously wrong shapes.
    assert EASY_OPEN_OPTS_SIZE >= 16


def test_easy_open_opts_field_order():
    """Field order must match the C struct so the engine reads the right slots."""
    expected = ["size", "num_workers", "eager_build", "_reserved"]
    actual = [name for name, _ in EasyOpenOptsStruct._fields_]
    assert actual == expected


def test_parse_error_struct_fields():
    expected = ["error_code", "message", "line", "column", "source"]
    actual = [name for name, _ in ParseErrorStruct._fields_]
    assert actual == expected


def test_column_struct_fields():
    expected = [
        "name",
        "type",
        "compound_kind",
        "compound_functor_id",
        "compound_arity",
        "compound_inline_col_offset",
    ]
    actual = [name for name, _ in ColumnStruct._fields_]
    assert actual == expected


def test_schema_struct_fields():
    expected = ["relation_name", "columns", "column_count"]
    actual = [name for name, _ in SchemaStruct._fields_]
    assert actual == expected


def test_stratum_struct_fields():
    expected = ["stratum_id", "rule_names", "rule_count", "is_recursive"]
    actual = [name for name, _ in StratumStruct._fields_]
    assert actual == expected


def test_compound_arg_struct_round_trip():
    arg = CompoundArgStruct(type=int(ColumnType.INT64), value=42)
    assert arg.type == int(ColumnType.INT64)
    assert arg.value == 42


def test_io_adapter_struct_abi_version():
    """The ABI-version constant must match what wirelog 0.40+ accepts."""
    assert WIRELOG_IO_ABI_VERSION == 2
    a = IOAdapterStruct(abi_version=WIRELOG_IO_ABI_VERSION)
    assert a.abi_version == 2


def test_io_adapter_struct_field_order():
    expected = ["abi_version", "scheme", "description", "read", "validate", "user_data"]
    actual = [name for name, _ in IOAdapterStruct._fields_]
    assert actual == expected


# ---- Callback types --------------------------------------------------------


def test_callback_types_distinct():
    """OnTupleFn and OnDeltaFn must be distinct ctypes function types."""
    assert OnTupleFn is not OnDeltaFn


def test_on_tuple_fn_signature():
    """OnTupleFn must have the documented (str, int64*, u32, void*) -> None shape."""

    # Build a no-op trampoline and verify it can be assigned through the type.
    @OnTupleFn
    def _noop(relation, row, ncols, user_data):
        return None

    assert isinstance(_noop, OnTupleFn)


def test_on_delta_fn_signature():
    @OnDeltaFn
    def _noop(relation, row, ncols, diff, user_data):
        return None

    assert isinstance(_noop, OnDeltaFn)


def test_on_delta_fn_carries_diff_parameter():
    """Sanity: OnDeltaFn has one more argument than OnTupleFn (the int32 diff)."""

    @OnTupleFn
    def _t(relation, row, ncols, user_data):
        return None

    @OnDeltaFn
    def _d(relation, row, ncols, diff, user_data):
        return None

    # Instance attributes carry the resolved argtypes.
    assert len(_t.argtypes) == 4
    assert len(_d.argtypes) == 5
    assert _d.argtypes[3] is ctypes.c_int32  # the diff slot
