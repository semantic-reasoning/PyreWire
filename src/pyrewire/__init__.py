"""PyreWire - Python wrapper for wirelog declarative dataflow analysis."""

__version__ = "0.41.0"
__author__ = "PyreWire Contributors"
__license__ = "Apache-2.0 OR GPL-3.0-or-later"

from pyrewire._core.errors import (
    CompoundBusyError,
    CompoundSaturatedError,
    ExecError,
    InvalidIRError,
    ParseError,
    WirelogError,
    WirelogInternError,
    WirelogIOError,
    WirelogMemoryError,
    WirelogModeError,
    WirelogVersionError,
)
from pyrewire._ffi._enums import (
    AggFn,
    ArithOp,
    BackendKind,
    CmpOp,
    ColumnType,
    CompoundKind,
    ErrorCode,
    IRNodeType,
    StrFn,
)
from pyrewire._ffi._util import (
    agg_fn_name,
    arith_op_name,
    build_config,
    cmp_op_name,
    wirelog_version,
)
from pyrewire.asyncio_session import (
    AsyncBatchProgram,
    AsyncEasySession,
    AsyncSession,
)
from pyrewire.batch import BatchProgram, Result
from pyrewire.compound import Compound, CompoundArg
from pyrewire.helpers import (
    Delta,
    is_wirelog_print_delta,
    make_safe_print_delta,
)
from pyrewire.io_adapter import (
    IOContext,
    register_adapter,
    registered_schemes,
    unregister_adapter,
)
from pyrewire.ir import IRNode
from pyrewire.program import Column, Program, Schema, Stratum
from pyrewire.session import EasySession, Session

__all__ = [
    "__version__",
    "Program",
    "Schema",
    "Column",
    "Stratum",
    "EasySession",
    "Session",
    "IRNode",
    "IRNodeType",
    "BatchProgram",
    "Result",
    "Compound",
    "CompoundArg",
    "Delta",
    "make_safe_print_delta",
    "is_wirelog_print_delta",
    "AsyncEasySession",
    "AsyncSession",
    "AsyncBatchProgram",
    "IOContext",
    "register_adapter",
    "unregister_adapter",
    "registered_schemes",
    "ColumnType",
    "CompoundKind",
    "BackendKind",
    "CmpOp",
    "ArithOp",
    "AggFn",
    "StrFn",
    "ErrorCode",
    "WirelogError",
    "ParseError",
    "InvalidIRError",
    "ExecError",
    "WirelogMemoryError",
    "WirelogIOError",
    "CompoundSaturatedError",
    "CompoundBusyError",
    "WirelogVersionError",
    "WirelogModeError",
    "WirelogInternError",
    "wirelog_version",
    "build_config",
    "cmp_op_name",
    "arith_op_name",
    "agg_fn_name",
]
