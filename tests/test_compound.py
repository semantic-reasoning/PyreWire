# SPDX-License-Identifier: Apache-2.0 OR GPL-3.0-or-later
"""Tests for `pyrewire.compound` (#23)."""

from __future__ import annotations

import ctypes

import pytest

from pyrewire._core.errors import (
    CompoundBusyError,
    CompoundSaturatedError,
    ExecError,
)
from pyrewire._ffi import LIB
from pyrewire._ffi._enums import ColumnType, ErrorCode
from pyrewire.compound import Compound, CompoundArg
from pyrewire.program import Program
from pyrewire.session import EasySession, Session

# ----------------------------------------------------------------------
# CompoundArg
# ----------------------------------------------------------------------


def test_compound_arg_to_struct_roundtrip():
    a = CompoundArg(ColumnType.INT32, 42)
    s = a.to_struct()
    assert int(s.type) == int(ColumnType.INT32)
    assert int(s.value) == 42


def test_compound_arg_string_value_is_intern_id():
    """`value` for a `STRING` column is the intern id, not the string."""
    a = CompoundArg(ColumnType.STRING, 7)
    assert a.to_struct().value == 7


# ----------------------------------------------------------------------
# Compound wrapper basics
# ----------------------------------------------------------------------


def test_null_handle_rejected():
    s = EasySession(".decl x(a: int32)\n")
    try:
        with pytest.raises(ValueError):
            Compound(s, "f", 1, 0)
    finally:
        s.close()


def test_handle_accessible_until_session_closes():
    s = EasySession(".decl x(a: int32)\n")
    c = Compound(s, "f", 1, 0xDEAD)
    assert c.handle == 0xDEAD
    s.close()
    with pytest.raises(ValueError):
        _ = c.handle


def test_explicit_invalidate():
    s = EasySession(".decl x(a: int32)\n")
    try:
        c = Compound(s, "f", 1, 0xCAFE)
        c.invalidate()
        with pytest.raises(ValueError):
            _ = c.handle
    finally:
        s.close()


def test_repr_includes_state():
    s = EasySession(".decl x(a: int32)\n")
    try:
        c = Compound(s, "name", 2, 0x100)
        r = repr(c)
        assert "name/2" in r
        c.invalidate()
        assert "invalid" in repr(c)
    finally:
        s.close()


def test_session_drop_invalidates_via_weakref():
    s = EasySession(".decl x(a: int32)\n")
    c = Compound(s, "f", 1, 0x123)
    del s
    import gc

    gc.collect()
    with pytest.raises(ValueError):
        _ = c.handle


# ----------------------------------------------------------------------
# EasySession.make_compound — happy path + error mapping
# ----------------------------------------------------------------------


def test_easy_make_compound_succeeds(monkeypatch):
    """Forward a known handle through `wirelog_easy_make_compound`."""

    def fake_make(_h, _functor, _n, _args, out):
        ctypes.cast(out, ctypes.POINTER(ctypes.c_uint64))[0] = 0xABCD
        return int(ErrorCode.OK)

    monkeypatch.setattr(LIB, "wirelog_easy_make_compound", fake_make)
    with EasySession(".decl x(a: int32)\n") as s:
        c = s.make_compound("pair", [CompoundArg(ColumnType.INT32, 1)])
        assert c.handle == 0xABCD
        assert c.functor == "pair"
        assert c.arity == 1


def test_easy_make_compound_null_handle_raises(monkeypatch):
    """An rc=OK + 0 handle is treated as ExecError."""

    def fake_make(_h, _functor, _n, _args, out):
        ctypes.cast(out, ctypes.POINTER(ctypes.c_uint64))[0] = 0
        return int(ErrorCode.OK)

    monkeypatch.setattr(LIB, "wirelog_easy_make_compound", fake_make)
    with EasySession(".decl x(a: int32)\n") as s:
        with pytest.raises(ExecError):
            s.make_compound("p", [CompoundArg(ColumnType.INT32, 1)])


def test_easy_make_compound_busy_surfaces(monkeypatch):
    def fake_make(_h, _functor, _n, _args, _out):
        return int(ErrorCode.COMPOUND_BUSY)

    monkeypatch.setattr(LIB, "wirelog_easy_make_compound", fake_make)
    with EasySession(".decl x(a: int32)\n") as s:
        with pytest.raises(CompoundBusyError):
            s.make_compound("p", [CompoundArg(ColumnType.INT32, 1)])


def test_easy_make_compound_saturated_surfaces(monkeypatch):
    def fake_make(_h, _functor, _n, _args, _out):
        return int(ErrorCode.COMPOUND_SATURATED)

    monkeypatch.setattr(LIB, "wirelog_easy_make_compound", fake_make)
    with EasySession(".decl x(a: int32)\n") as s:
        with pytest.raises(CompoundSaturatedError):
            s.make_compound("p", [CompoundArg(ColumnType.INT32, 1)])


def test_easy_compounds_invalidated_on_close(monkeypatch):
    def fake_make(_h, _functor, _n, _args, out):
        ctypes.cast(out, ctypes.POINTER(ctypes.c_uint64))[0] = 0xFEED
        return int(ErrorCode.OK)

    monkeypatch.setattr(LIB, "wirelog_easy_make_compound", fake_make)
    s = EasySession(".decl x(a: int32)\n")
    c = s.make_compound("p", [CompoundArg(ColumnType.INT32, 1)])
    s.close()
    with pytest.raises(ValueError):
        _ = c.handle


# ----------------------------------------------------------------------
# Session.make_compound mirrors the EasySession behaviour
# ----------------------------------------------------------------------


def _simple_program() -> Program:
    return Program.from_string(".decl x(a: int32)\n")


def test_session_make_compound_succeeds(monkeypatch):
    def fake_make(_h, _functor, _n, _args, out):
        ctypes.cast(out, ctypes.POINTER(ctypes.c_uint64))[0] = 0x4242
        return int(ErrorCode.OK)

    monkeypatch.setattr(LIB, "wirelog_session_make_compound", fake_make)
    prog = _simple_program()
    with Session(prog) as s:
        c = s.make_compound("p", [CompoundArg(ColumnType.INT32, 1)])
        assert c.handle == 0x4242


def test_session_compounds_invalidated_on_close(monkeypatch):
    def fake_make(_h, _functor, _n, _args, out):
        ctypes.cast(out, ctypes.POINTER(ctypes.c_uint64))[0] = 0x55
        return int(ErrorCode.OK)

    monkeypatch.setattr(LIB, "wirelog_session_make_compound", fake_make)
    prog = _simple_program()
    s = Session(prog)
    c = s.make_compound("p", [CompoundArg(ColumnType.INT32, 1)])
    s.close()
    with pytest.raises(ValueError):
        _ = c.handle


def test_session_make_compound_empty_args(monkeypatch):
    def fake_make(_h, _functor, n, _args, out):
        assert int(n.value if hasattr(n, "value") else n) == 0
        ctypes.cast(out, ctypes.POINTER(ctypes.c_uint64))[0] = 0xA
        return int(ErrorCode.OK)

    monkeypatch.setattr(LIB, "wirelog_session_make_compound", fake_make)
    prog = _simple_program()
    with Session(prog) as s:
        c = s.make_compound("p", [])
        assert c.handle == 0xA
        assert c.arity == 0
