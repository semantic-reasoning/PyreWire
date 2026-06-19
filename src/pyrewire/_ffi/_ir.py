# SPDX-License-Identifier: Apache-2.0 OR GPL-3.0-or-later
"""Raw ctypes bindings for wirelog's IR-inspection entry points.

Six functions from `wirelog/wirelog-ir.h`:

- `wirelog_ir_node_get_type(node) -> wirelog_ir_node_type_t`
- `wirelog_ir_node_get_relation_name(node) -> const char *`
- `wirelog_ir_node_get_child_count(node) -> uint32_t`
- `wirelog_ir_node_get_child(node, index) -> const wirelog_ir_node_t *`
- `wirelog_ir_node_print(node, indent) -> void`
- `wirelog_ir_node_to_string(node) -> char *`  (caller frees)

`to_string` is bound as `POINTER(c_char)` (not `c_char_p`) so the
wrapper in #25 can `libc_free` the heap buffer after copying.
"""

from __future__ import annotations

import ctypes

from . import LIB
from ._types import IRNodeHandle


def _register() -> None:
    LIB.wirelog_ir_node_get_type.restype = ctypes.c_int
    LIB.wirelog_ir_node_get_type.argtypes = [IRNodeHandle]

    LIB.wirelog_ir_node_get_relation_name.restype = ctypes.c_char_p
    LIB.wirelog_ir_node_get_relation_name.argtypes = [IRNodeHandle]

    LIB.wirelog_ir_node_get_child_count.restype = ctypes.c_uint32
    LIB.wirelog_ir_node_get_child_count.argtypes = [IRNodeHandle]

    LIB.wirelog_ir_node_get_child.restype = IRNodeHandle
    LIB.wirelog_ir_node_get_child.argtypes = [IRNodeHandle, ctypes.c_uint32]

    LIB.wirelog_ir_node_print.restype = None
    LIB.wirelog_ir_node_print.argtypes = [IRNodeHandle, ctypes.c_uint32]

    # caller frees the returned string; use POINTER(c_char) so the
    # raw address survives for libc_free, instead of being consumed
    # by ctypes' c_char_p conversion to a Python bytes copy.
    LIB.wirelog_ir_node_to_string.restype = ctypes.POINTER(ctypes.c_char)
    LIB.wirelog_ir_node_to_string.argtypes = [IRNodeHandle]


_register()
