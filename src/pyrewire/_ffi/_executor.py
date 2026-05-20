"""Raw ctypes bindings for wirelog's batch-executor surface (#16).

Covers:

- `wirelog_executor_create(prog, &error) -> wirelog_executor_t *`
- `wirelog_executor_free(exec) -> void`
- `wirelog_load_facts_from_csv(exec, rel, csv, &error) -> bool`
- `wirelog_evaluate(exec, &error) -> wirelog_result_t *`
- `wirelog_result_get_relation(res, rel) -> const void *`
- `wirelog_result_relation_cardinality(res, rel) -> uint64_t`
- `wirelog_result_write_csv(res, rel, path, &error) -> bool`
- `wirelog_result_free(res) -> void`

The high-level `BatchProgram` (#17) and `Result` (#18) build on top.
"""

from __future__ import annotations

import ctypes

from . import LIB
from ._types import ExecutorHandle, ProgramHandle, ResultHandle


def _register() -> None:
    err = ctypes.POINTER(ctypes.c_int)

    LIB.wirelog_executor_create.restype = ExecutorHandle
    LIB.wirelog_executor_create.argtypes = [ProgramHandle, err]

    LIB.wirelog_executor_free.restype = None
    LIB.wirelog_executor_free.argtypes = [ExecutorHandle]

    LIB.wirelog_load_facts_from_csv.restype = ctypes.c_bool
    LIB.wirelog_load_facts_from_csv.argtypes = [
        ExecutorHandle,
        ctypes.c_char_p,
        ctypes.c_char_p,
        err,
    ]

    LIB.wirelog_evaluate.restype = ResultHandle
    LIB.wirelog_evaluate.argtypes = [ExecutorHandle, err]

    LIB.wirelog_result_get_relation.restype = ctypes.c_void_p
    LIB.wirelog_result_get_relation.argtypes = [ResultHandle, ctypes.c_char_p]

    LIB.wirelog_result_relation_cardinality.restype = ctypes.c_uint64
    LIB.wirelog_result_relation_cardinality.argtypes = [
        ResultHandle,
        ctypes.c_char_p,
    ]

    LIB.wirelog_result_write_csv.restype = ctypes.c_bool
    LIB.wirelog_result_write_csv.argtypes = [
        ResultHandle,
        ctypes.c_char_p,
        ctypes.c_char_p,
        err,
    ]

    LIB.wirelog_result_free.restype = None
    LIB.wirelog_result_free.argtypes = [ResultHandle]


_register()
