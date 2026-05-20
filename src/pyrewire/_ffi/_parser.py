"""Raw ctypes bindings for wirelog's parser, program introspection, and
optimizer / fact-loading entry points.

Covers:

- `wirelog_parse`, `wirelog_parse_string`, `wirelog_parse_with_error_info`
- `wirelog_program_free`
- `wirelog_program_get_stratum_count`, `wirelog_program_get_stratum`
- `wirelog_program_get_rule_count`
- `wirelog_program_get_schema`, `wirelog_program_is_stratified`
- `wirelog_program_get_facts`, `wirelog_program_get_intern`
- `wirelog_load_all_facts`, `wirelog_load_input_files`
- `wirelog_optimize`, `wirelog_optimizer_debug`

This module only registers argtypes/restype on the shared `LIB` handle.
The high-level `Program` class (issue #14), `Program.facts` (issue #15),
and `BatchProgram` (issue #17) build on top.
"""

from __future__ import annotations

import ctypes

from . import LIB
from ._types import (
    InternHandle,
    ParseErrorStruct,
    ProgramHandle,
    SchemaStruct,
    StratumStruct,
)


def _register() -> None:
    err = ctypes.POINTER(ctypes.c_int)

    LIB.wirelog_parse.restype = ProgramHandle
    LIB.wirelog_parse.argtypes = [ctypes.c_char_p, err]

    LIB.wirelog_parse_string.restype = ProgramHandle
    LIB.wirelog_parse_string.argtypes = [ctypes.c_char_p, err]

    LIB.wirelog_parse_with_error_info.restype = ProgramHandle
    LIB.wirelog_parse_with_error_info.argtypes = [
        ctypes.c_char_p,
        ctypes.POINTER(ParseErrorStruct),
    ]

    LIB.wirelog_program_free.restype = None
    LIB.wirelog_program_free.argtypes = [ProgramHandle]

    LIB.wirelog_program_get_stratum_count.restype = ctypes.c_uint32
    LIB.wirelog_program_get_stratum_count.argtypes = [ProgramHandle]

    LIB.wirelog_program_get_stratum.restype = ctypes.POINTER(StratumStruct)
    LIB.wirelog_program_get_stratum.argtypes = [ProgramHandle, ctypes.c_uint32]

    LIB.wirelog_program_get_rule_count.restype = ctypes.c_uint32
    LIB.wirelog_program_get_rule_count.argtypes = [ProgramHandle]

    LIB.wirelog_program_get_schema.restype = ctypes.POINTER(SchemaStruct)
    LIB.wirelog_program_get_schema.argtypes = [ProgramHandle, ctypes.c_char_p]

    LIB.wirelog_program_is_stratified.restype = ctypes.c_bool
    LIB.wirelog_program_is_stratified.argtypes = [ProgramHandle]

    LIB.wirelog_program_get_facts.restype = ctypes.c_int
    LIB.wirelog_program_get_facts.argtypes = [
        ProgramHandle,
        ctypes.c_char_p,
        ctypes.POINTER(ctypes.POINTER(ctypes.c_int64)),
        ctypes.POINTER(ctypes.c_uint32),
        ctypes.POINTER(ctypes.c_uint32),
    ]

    LIB.wirelog_program_get_intern.restype = InternHandle
    LIB.wirelog_program_get_intern.argtypes = [ProgramHandle]

    LIB.wirelog_load_all_facts.restype = ctypes.c_int
    LIB.wirelog_load_all_facts.argtypes = [ProgramHandle, ctypes.c_void_p]

    LIB.wirelog_load_input_files.restype = ctypes.c_int
    LIB.wirelog_load_input_files.argtypes = [ProgramHandle, ctypes.c_void_p]

    LIB.wirelog_optimize.restype = ctypes.c_bool
    LIB.wirelog_optimize.argtypes = [ProgramHandle, err]

    LIB.wirelog_optimizer_debug.restype = None
    LIB.wirelog_optimizer_debug.argtypes = [ProgramHandle]


_register()
