# SPDX-License-Identifier: Apache-2.0 OR GPL-3.0-or-later
"""Lazy Python wrapper around a `wirelog_ir_node_t *` (#25).

`IRNode` does not own the C pointer — the IR tree lives inside the
parent program — but it must `libc_free` the heap string returned by
`wirelog_ir_node_to_string`.
"""

from __future__ import annotations

import ctypes
from collections.abc import Iterator

from pyrewire._core._libc import libc_free
from pyrewire._ffi import LIB
from pyrewire._ffi import _ir as _ir_ffi  # noqa: F401  -- registers argtypes
from pyrewire._ffi._enums import IRNodeType
from pyrewire._ffi._types import IRNodeHandle


class IRNode:
    """Lazy wrapper over `wirelog_ir_node_t`. Does not own the pointer."""

    __slots__ = ("_handle",)

    def __init__(self, handle: IRNodeHandle) -> None:
        if not handle:
            raise ValueError("null IR node handle")
        self._handle = handle

    @property
    def type(self) -> IRNodeType:
        return IRNodeType(int(LIB.wirelog_ir_node_get_type(self._handle)))

    @property
    def relation_name(self) -> str:
        s = LIB.wirelog_ir_node_get_relation_name(self._handle)
        if not s:
            return ""
        return bytes(s).decode("utf-8", errors="replace")

    @property
    def child_count(self) -> int:
        return int(LIB.wirelog_ir_node_get_child_count(self._handle))

    def child(self, index: int) -> IRNode | None:
        h = LIB.wirelog_ir_node_get_child(self._handle, ctypes.c_uint32(index))
        if not h:
            return None
        return IRNode(IRNodeHandle(h))

    def children(self) -> Iterator[IRNode]:
        for i in range(self.child_count):
            c = self.child(i)
            if c is not None:
                yield c

    def walk(self) -> Iterator[IRNode]:
        """Pre-order traversal: yields self, then each child's `walk()`."""
        yield self
        for c in self.children():
            yield from c.walk()

    def to_str(self) -> str:
        """Render this node via `wirelog_ir_node_to_string`.

        The heap buffer is always freed — including on decode errors —
        because `string_at` copies into a Python `bytes` before the
        `finally` block runs.
        """
        ptr = LIB.wirelog_ir_node_to_string(self._handle)
        if not ptr:
            return ""
        try:
            return ctypes.string_at(ptr).decode("utf-8", errors="replace")
        finally:
            libc_free(ptr)

    def print(self, indent: int = 0) -> None:
        """Call `wirelog_ir_node_print` (writes to stdout). Debug aid."""
        LIB.wirelog_ir_node_print(self._handle, ctypes.c_uint32(indent))

    def __repr__(self) -> str:
        return f"IRNode({self.type.name}, relation={self.relation_name!r})"


__all__ = ["IRNode"]
