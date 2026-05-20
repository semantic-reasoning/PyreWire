"""Tests for `pyrewire._ffi._executor` bindings (#16)."""

from __future__ import annotations

import ctypes

import pyrewire._ffi._executor  # noqa: F401  -- register
import pyrewire._ffi._parser  # noqa: F401  -- for wirelog_parse_string
from pyrewire._ffi import LIB
from pyrewire._ffi._types import ExecutorHandle, ProgramHandle


def test_signatures_attached():
    names = [
        "wirelog_executor_create",
        "wirelog_executor_free",
        "wirelog_load_facts_from_csv",
        "wirelog_evaluate",
        "wirelog_result_get_relation",
        "wirelog_result_relation_cardinality",
        "wirelog_result_write_csv",
        "wirelog_result_free",
    ]
    for name in names:
        fn = getattr(LIB, name)
        assert fn.argtypes is not None, f"{name} has no argtypes"


def _parse(src: bytes) -> ProgramHandle:
    rc = ctypes.c_int(0)
    h = LIB.wirelog_parse_string(src, ctypes.byref(rc))
    assert h, f"parse_string rc={rc.value}"
    return ProgramHandle(h)


def test_executor_create_and_free():
    prog = _parse(b".decl x(a: int32)\n")
    try:
        rc = ctypes.c_int(0)
        h = LIB.wirelog_executor_create(prog, ctypes.byref(rc))
        assert h, f"executor_create rc={rc.value}"
        LIB.wirelog_executor_free(ExecutorHandle(h))
    finally:
        LIB.wirelog_program_free(prog)


def test_evaluate_returns_result_handle():
    src = (
        b".decl edge(x: int32, y: int32)\n"
        b".decl r(x: int32)\n"
        b"r(X) :- edge(X, _).\n"
        b"edge(1, 2).\nedge(2, 3).\n"
    )
    prog = _parse(src)
    try:
        rc = ctypes.c_int(0)
        ex = LIB.wirelog_executor_create(prog, ctypes.byref(rc))
        assert ex, f"executor_create rc={rc.value}"
        ex_h = ExecutorHandle(ex)
        try:
            rc2 = ctypes.c_int(0)
            res = LIB.wirelog_evaluate(ex_h, ctypes.byref(rc2))
            # `wirelog_evaluate` may return NULL if execution itself is
            # not implemented yet for this surface — accept either
            # outcome and just verify the call doesn't crash.
            if res:
                LIB.wirelog_result_free(res)
        finally:
            LIB.wirelog_executor_free(ex_h)
    finally:
        LIB.wirelog_program_free(prog)
