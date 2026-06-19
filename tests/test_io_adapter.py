# SPDX-License-Identifier: Apache-2.0 OR GPL-3.0-or-later
"""Tests for `pyrewire.io_adapter` (#27)."""

from __future__ import annotations

import ctypes
from typing import Any

import pytest

import pyrewire.io_adapter as io_adapter_mod
from pyrewire._core.errors import WirelogIOError
from pyrewire._ffi import LIB
from pyrewire.io_adapter import (
    IOContext,
    register_adapter,
    registered_schemes,
    unregister_adapter,
)


# Use unique scheme names per test to avoid cross-test interference even
# if a failure leaves a scheme registered (the registry is process-wide).
def _scheme(name: str) -> str:
    return f"pytest_io_{name}"


def test_register_and_unregister_roundtrip():
    scheme = _scheme("basic")

    @register_adapter(scheme, description="basic test adapter")
    class _A:
        def read(self, ctx: IOContext) -> list[list[int]]:
            return []

    assert scheme in registered_schemes()
    unregister_adapter(scheme)
    assert scheme not in registered_schemes()


def test_unregister_unknown_scheme_is_noop():
    """Unregistering a scheme that was never registered is silent."""
    unregister_adapter(_scheme("never_registered_xyz"))


def test_register_returns_class_unchanged():
    scheme = _scheme("identity")

    @register_adapter(scheme)
    class _A:
        def read(self, ctx: IOContext) -> list[list[int]]:
            return []

    try:
        # The decorator returns the class itself.
        assert _A.__name__ == "_A"
    finally:
        unregister_adapter(scheme)


def test_register_rejects_empty_scheme():
    with pytest.raises(ValueError):

        @register_adapter("")
        class _A:
            def read(self, ctx: IOContext) -> list[list[int]]:
                return []


def test_register_wraps_failure_in_wirelog_io_error(monkeypatch):
    """If wirelog rejects the registration, the wrapper surfaces it."""

    def fake_register(_p: Any) -> int:
        return -1

    def fake_last_error() -> bytes:
        return b"forced failure"

    monkeypatch.setattr(LIB, "wirelog_io_register_adapter", fake_register)
    monkeypatch.setattr(LIB, "wirelog_io_last_error", fake_last_error)

    with pytest.raises(WirelogIOError, match="forced failure"):

        @register_adapter(_scheme("fail"))
        class _A:
            def read(self, ctx: IOContext) -> list[list[int]]:
                return []


def test_unregister_failure_raises(monkeypatch):
    scheme = _scheme("unreg_fail")

    @register_adapter(scheme)
    class _A:
        def read(self, ctx: IOContext) -> list[list[int]]:
            return []

    def fake_unregister(_s: Any) -> int:
        return -1

    def fake_last_error() -> bytes:
        return b"forced unregister failure"

    try:
        monkeypatch.setattr(LIB, "wirelog_io_unregister_adapter", fake_unregister)
        monkeypatch.setattr(LIB, "wirelog_io_last_error", fake_last_error)
        with pytest.raises(WirelogIOError, match="forced unregister failure"):
            unregister_adapter(scheme)
    finally:
        # Tear down the registry slot directly — wirelog still owns the
        # underlying scheme but the adapter struct is harmless once Python
        # drops its keep-alive references.
        io_adapter_mod._REGISTRY.pop(scheme, None)


def test_io_context_reads_relation_name_via_ffi(monkeypatch):
    """`IOContext.relation_name` returns the decoded scheme bytes."""
    monkeypatch.setattr(LIB, "wirelog_io_ctx_relation_name", lambda _c: b"edges")
    ctx = IOContext(ctypes.c_void_p(0xDEADBEEF))
    assert ctx.relation_name == "edges"


def test_io_context_num_cols(monkeypatch):
    monkeypatch.setattr(LIB, "wirelog_io_ctx_num_cols", lambda _c: 3)
    ctx = IOContext(ctypes.c_void_p(0xDEADBEEF))
    assert ctx.num_cols == 3


def test_io_context_param_none_when_missing(monkeypatch):
    monkeypatch.setattr(LIB, "wirelog_io_ctx_param", lambda _c, _k: None)
    ctx = IOContext(ctypes.c_void_p(0xDEADBEEF))
    assert ctx.param("missing") is None


def test_io_context_intern_string(monkeypatch):
    monkeypatch.setattr(LIB, "wirelog_io_ctx_intern_string", lambda _c, _b: 7)
    ctx = IOContext(ctypes.c_void_p(0xDEADBEEF))
    assert ctx.intern_string("alice") == 7


# ----------------------------------------------------------------------
# Read / validate trampolines
# ----------------------------------------------------------------------


def _build_read_trampoline(py_instance: Any) -> Any:
    return io_adapter_mod._build_read_cfunc(py_instance)


def test_read_callback_swallows_python_exception():
    class Boom:
        def read(self, ctx: IOContext) -> list[list[int]]:
            raise RuntimeError("kaboom")

    read_fn = _build_read_trampoline(Boom())
    out_data = ctypes.POINTER(ctypes.c_int64)()
    out_n = ctypes.c_uint32(0)
    rc = read_fn(
        ctypes.c_void_p(0),
        ctypes.byref(out_data),
        ctypes.byref(out_n),
        None,
    )
    assert rc == -1


def test_read_callback_zero_rows(monkeypatch):
    monkeypatch.setattr(LIB, "wirelog_io_ctx_num_cols", lambda _c: 2)

    class Empty:
        def read(self, ctx: IOContext) -> list[list[int]]:
            return []

    read_fn = _build_read_trampoline(Empty())
    out_data = ctypes.POINTER(ctypes.c_int64)()
    out_n = ctypes.c_uint32(99)
    rc = read_fn(
        ctypes.c_void_p(0),
        ctypes.byref(out_data),
        ctypes.byref(out_n),
        None,
    )
    assert rc == 0
    assert out_n.value == 0


def test_read_callback_rejects_wrong_arity(monkeypatch):
    monkeypatch.setattr(LIB, "wirelog_io_ctx_num_cols", lambda _c: 2)

    class BadShape:
        def read(self, ctx: IOContext) -> list[list[int]]:
            return [[1]]  # ncols=2 expected

    read_fn = _build_read_trampoline(BadShape())
    out_data = ctypes.POINTER(ctypes.c_int64)()
    out_n = ctypes.c_uint32(0)
    rc = read_fn(
        ctypes.c_void_p(0),
        ctypes.byref(out_data),
        ctypes.byref(out_n),
        None,
    )
    assert rc == -1


def test_read_callback_succeeds(monkeypatch):
    monkeypatch.setattr(LIB, "wirelog_io_ctx_num_cols", lambda _c: 2)

    class OK:
        def read(self, ctx: IOContext) -> list[list[int]]:
            return [[1, 2], [3, 4]]

    read_fn = _build_read_trampoline(OK())
    out_data = ctypes.POINTER(ctypes.c_int64)()
    out_n = ctypes.c_uint32(0)
    rc = read_fn(
        ctypes.c_void_p(0),
        ctypes.byref(out_data),
        ctypes.byref(out_n),
        None,
    )
    assert rc == 0
    assert out_n.value == 2
    # Read back the malloc'd buffer.
    vals = [out_data[i] for i in range(2 * 2)]
    assert vals == [1, 2, 3, 4]


def test_validate_noop_when_method_absent():
    class NoValidate:
        def read(self, ctx: IOContext) -> list[list[int]]:
            return []

    validate_fn = io_adapter_mod._build_validate_cfunc(NoValidate())
    rc = validate_fn(ctypes.c_void_p(0), None, 0, None)
    assert rc == 0


def test_validate_failure_copies_message():
    class WithValidate:
        def read(self, ctx: IOContext) -> list[list[int]]:
            return []

        def validate(self, ctx: IOContext) -> None:
            raise ValueError("bad input")

    validate_fn = io_adapter_mod._build_validate_cfunc(WithValidate())
    errbuf = ctypes.create_string_buffer(64)
    rc = validate_fn(ctypes.c_void_p(0), errbuf, 64, None)
    assert rc == -1
    assert b"bad input" in errbuf.value
