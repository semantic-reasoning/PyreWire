# SPDX-License-Identifier: Apache-2.0 OR GPL-3.0-or-later
"""Tests for `pyrewire._ffi._parser` bindings."""

from __future__ import annotations

import ctypes

import pyrewire._ffi._parser  # noqa: F401  -- registers argtypes/restype
from pyrewire._ffi import LIB
from pyrewire._ffi._types import ProgramHandle


def test_signatures_attached():
    """Every parser / introspection entry point has a configured restype."""
    names = [
        "wirelog_parse",
        "wirelog_parse_string",
        "wirelog_parse_with_error_info",
        "wirelog_program_free",
        "wirelog_program_get_stratum_count",
        "wirelog_program_get_stratum",
        "wirelog_program_get_rule_count",
        "wirelog_program_get_schema",
        "wirelog_program_is_stratified",
        "wirelog_program_get_facts",
        "wirelog_program_get_intern",
        "wirelog_load_all_facts",
        "wirelog_load_input_files",
        "wirelog_optimize",
        "wirelog_optimizer_debug",
    ]
    for name in names:
        fn = getattr(LIB, name)
        assert fn.argtypes is not None, f"{name} has no argtypes set"


def test_parse_string_simple_program():
    rc = ctypes.c_int(0)
    src = b".decl x(a: int32)\n"
    prog = LIB.wirelog_parse_string(src, ctypes.byref(rc))
    assert prog, f"parse_string returned NULL (rc={rc.value})"
    LIB.wirelog_program_free(ProgramHandle(prog))


def test_parse_string_invalid_source_returns_null():
    rc = ctypes.c_int(0)
    prog = LIB.wirelog_parse_string(b"this is not datalog", ctypes.byref(rc))
    assert not prog, "expected NULL on parse error"
    assert rc.value != 0, "expected non-zero error code"


def test_program_get_stratum_count_non_zero_for_program_with_rule():
    rc = ctypes.c_int(0)
    src = b".decl edge(x: int32, y: int32)\n.decl r(x: int32)\nr(X) :- edge(X, _).\n"
    prog = LIB.wirelog_parse_string(src, ctypes.byref(rc))
    assert prog
    try:
        n = LIB.wirelog_program_get_stratum_count(ProgramHandle(prog))
        assert n >= 1
    finally:
        LIB.wirelog_program_free(ProgramHandle(prog))


def test_program_is_stratified():
    rc = ctypes.c_int(0)
    src = b".decl a(x: int32)\n.decl b(x: int32)\nb(X) :- a(X).\n"
    prog = LIB.wirelog_parse_string(src, ctypes.byref(rc))
    assert prog
    try:
        assert LIB.wirelog_program_is_stratified(ProgramHandle(prog))
    finally:
        LIB.wirelog_program_free(ProgramHandle(prog))
