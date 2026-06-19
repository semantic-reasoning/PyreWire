# SPDX-License-Identifier: Apache-2.0 OR GPL-3.0-or-later
"""Tests for `pyrewire._ffi._ir` bindings (#24)."""

from __future__ import annotations

import ctypes

import pyrewire._ffi._ir  # noqa: F401  -- registers argtypes/restype
from pyrewire._ffi import LIB
from pyrewire._ffi._enums import IRNodeType


def test_signatures_attached():
    names = [
        "wirelog_ir_node_get_type",
        "wirelog_ir_node_get_relation_name",
        "wirelog_ir_node_get_child_count",
        "wirelog_ir_node_get_child",
        "wirelog_ir_node_print",
        "wirelog_ir_node_to_string",
    ]
    for name in names:
        fn = getattr(LIB, name)
        assert fn.argtypes is not None, f"{name} has no argtypes"


def test_to_string_restype_is_pointer_not_c_char_p():
    """`POINTER(c_char)` keeps the raw pointer; `c_char_p` would copy
    and drop the original, leaking the heap buffer."""
    assert LIB.wirelog_ir_node_to_string.restype is ctypes.POINTER(ctypes.c_char)
    assert LIB.wirelog_ir_node_to_string.restype is not ctypes.c_char_p


def test_irnode_type_enum_matches_header_order():
    """The enum order is load-bearing: it must match wirelog-ir.h."""
    assert IRNodeType.SCAN == 0
    assert IRNodeType.PROJECT == 1
    assert IRNodeType.FILTER == 2
    assert IRNodeType.JOIN == 3
    assert IRNodeType.FLATMAP == 4
    assert IRNodeType.AGGREGATE == 5
    assert IRNodeType.ANTIJOIN == 6
    assert IRNodeType.UNION == 7
    assert IRNodeType.SEMIJOIN == 8
    assert IRNodeType.COMPOUND_INLINE == 9
    assert IRNodeType.COMPOUND_SIDE == 10
