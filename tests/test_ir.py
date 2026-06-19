# SPDX-License-Identifier: Apache-2.0 OR GPL-3.0-or-later
"""Tests for `pyrewire.ir.IRNode` (#25).

The acceptance criterion calls for walking a real IR tree, but no public
`Program.ir_root()` accessor exists in wirelog yet (a follow-up issue
will add it once wirelog exposes the entry point). The fixtures below
exercise the wrapper against monkey-patched FFI functions, which is
enough to cover every code path — the FFI signatures themselves are
already validated in `test_ir_ffi.py` against the real library.
"""

from __future__ import annotations

import ctypes
from typing import Any

import pytest

import pyrewire._ffi._ir  # noqa: F401  -- registers argtypes/restype
import pyrewire.ir as ir_mod
from pyrewire._core._libc import libc_malloc
from pyrewire._ffi import LIB
from pyrewire._ffi._enums import IRNodeType
from pyrewire._ffi._types import IRNodeHandle
from pyrewire.ir import IRNode

CharPtr = ctypes.POINTER(ctypes.c_char)


class _FakeIR:
    """Holds attribute mocks keyed by an integer "node id" we use as a
    fake pointer. Maps each id to its type / relation_name / children."""

    def __init__(self) -> None:
        self.nodes: dict[int, dict[str, Any]] = {}

    def add(
        self,
        node_id: int,
        type_: int,
        relation: bytes | None = b"",
        children: list[int] | None = None,
    ) -> None:
        self.nodes[node_id] = {
            "type": type_,
            "relation": relation,
            "children": list(children or []),
        }


@pytest.fixture
def fake_ir(monkeypatch):
    fake = _FakeIR()

    def get_type(handle: Any) -> int:
        return int(fake.nodes[_addr(handle)]["type"])

    def get_relation_name(handle: Any) -> bytes | None:
        return fake.nodes[_addr(handle)]["relation"]

    def get_child_count(handle: Any) -> int:
        return len(fake.nodes[_addr(handle)]["children"])

    def get_child(handle: Any, index: Any) -> int:
        idx = int(getattr(index, "value", index))
        kids = fake.nodes[_addr(handle)]["children"]
        return kids[idx] if 0 <= idx < len(kids) else 0

    monkeypatch.setattr(LIB, "wirelog_ir_node_get_type", get_type)
    monkeypatch.setattr(LIB, "wirelog_ir_node_get_relation_name", get_relation_name)
    monkeypatch.setattr(LIB, "wirelog_ir_node_get_child_count", get_child_count)
    monkeypatch.setattr(LIB, "wirelog_ir_node_get_child", get_child)
    return fake


def _addr(handle: Any) -> int:
    """Extract an integer key from whatever shape IRNodeHandle is in."""
    if isinstance(handle, int):
        return handle
    v = getattr(handle, "value", None)
    return int(v) if v is not None else 0


def test_init_rejects_null_handle():
    with pytest.raises(ValueError):
        IRNode(IRNodeHandle(0))


def test_type_enum(monkeypatch, fake_ir):
    fake_ir.add(1, type_=IRNodeType.FILTER.value, relation=b"edge")
    n = IRNode(IRNodeHandle(1))
    assert n.type == IRNodeType.FILTER


def test_relation_name_decoded(monkeypatch, fake_ir):
    fake_ir.add(1, type_=IRNodeType.SCAN.value, relation=b"edge")
    n = IRNode(IRNodeHandle(1))
    assert n.relation_name == "edge"


def test_relation_name_empty_when_null(monkeypatch, fake_ir):
    fake_ir.add(1, type_=IRNodeType.SCAN.value, relation=None)
    n = IRNode(IRNodeHandle(1))
    assert n.relation_name == ""


def test_child_count(monkeypatch, fake_ir):
    fake_ir.add(1, type_=IRNodeType.JOIN.value, children=[2, 3])
    fake_ir.add(2, type_=IRNodeType.SCAN.value)
    fake_ir.add(3, type_=IRNodeType.SCAN.value)
    n = IRNode(IRNodeHandle(1))
    assert n.child_count == 2


def test_child_returns_none_at_out_of_range(monkeypatch, fake_ir):
    fake_ir.add(1, type_=IRNodeType.SCAN.value)
    n = IRNode(IRNodeHandle(1))
    assert n.child(0) is None


def test_walk_order_preorder(monkeypatch, fake_ir):
    # root [JOIN] -> child [FILTER] -> grandchild [SCAN]
    fake_ir.add(1, type_=IRNodeType.JOIN.value, children=[2])
    fake_ir.add(2, type_=IRNodeType.FILTER.value, children=[3])
    fake_ir.add(3, type_=IRNodeType.SCAN.value)
    root = IRNode(IRNodeHandle(1))
    order = [n.type for n in root.walk()]
    assert order == [IRNodeType.JOIN, IRNodeType.FILTER, IRNodeType.SCAN]


def test_children_iterator_yields_in_order(monkeypatch, fake_ir):
    fake_ir.add(1, type_=IRNodeType.UNION.value, children=[2, 3])
    fake_ir.add(2, type_=IRNodeType.SCAN.value, relation=b"a")
    fake_ir.add(3, type_=IRNodeType.SCAN.value, relation=b"b")
    root = IRNode(IRNodeHandle(1))
    names = [c.relation_name for c in root.children()]
    assert names == ["a", "b"]


def test_to_str_roundtrip_and_free(monkeypatch):
    """`to_str` must copy via `string_at` and `libc_free` the buffer
    exactly once, even when decode happens cleanly."""
    payload = b"SCAN(edge)"
    addr = libc_malloc(len(payload) + 1)
    assert addr, "libc_malloc returned NULL"
    ctypes.memmove(addr, payload + b"\0", len(payload) + 1)

    returned = {"ptr": addr}

    def to_string(handle: Any) -> Any:
        return ctypes.cast(returned["ptr"], CharPtr)

    freed: list[int] = []
    real_free = ir_mod.libc_free

    def tracking_free(ptr: Any) -> None:
        freed.append(int(ctypes.cast(ptr, ctypes.c_void_p).value or 0))
        real_free(ptr)

    monkeypatch.setattr(LIB, "wirelog_ir_node_to_string", to_string)
    monkeypatch.setattr(ir_mod, "libc_free", tracking_free)

    # We need a working `wirelog_ir_node_get_type` so __repr__/assertions
    # don't blow up — but `to_str` itself doesn't call it.
    n = IRNode(IRNodeHandle(0xDEADBEEF))
    assert n.to_str() == "SCAN(edge)"
    assert freed == [addr], f"expected free({addr}), got {freed}"


def test_to_str_returns_empty_on_null(monkeypatch):
    def to_string(handle: Any) -> Any:
        return ctypes.cast(0, CharPtr)

    monkeypatch.setattr(LIB, "wirelog_ir_node_to_string", to_string)
    n = IRNode(IRNodeHandle(0xCAFEF00D))
    assert n.to_str() == ""


def test_repr_contains_type_and_relation(monkeypatch, fake_ir):
    fake_ir.add(1, type_=IRNodeType.AGGREGATE.value, relation=b"counts")
    n = IRNode(IRNodeHandle(1))
    r = repr(n)
    assert "AGGREGATE" in r
    assert "counts" in r


def test_print_invokes_ffi(monkeypatch, fake_ir):
    fake_ir.add(1, type_=IRNodeType.SCAN.value)
    seen: list[tuple[Any, Any]] = []

    def fake_print(handle: Any, indent: Any) -> None:
        seen.append((_addr(handle), int(getattr(indent, "value", indent))))

    monkeypatch.setattr(LIB, "wirelog_ir_node_print", fake_print)
    n = IRNode(IRNodeHandle(1))
    n.print(indent=4)
    assert seen == [(1, 4)]
