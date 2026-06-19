# SPDX-License-Identifier: Apache-2.0 OR GPL-3.0-or-later
"""Tests for `pyrewire._ffi._io` bindings (#26)."""

from __future__ import annotations

import ctypes

import pyrewire._ffi._io  # noqa: F401  -- register argtypes/restype
from pyrewire._ffi import LIB
from pyrewire._ffi._types import WIRELOG_IO_ABI_VERSION, IOAdapterStruct


def test_signatures_attached():
    names = [
        "wirelog_io_register_adapter",
        "wirelog_io_unregister_adapter",
        "wirelog_io_find_adapter",
        "wirelog_io_last_error",
        "wirelog_io_ctx_relation_name",
        "wirelog_io_ctx_num_cols",
        "wirelog_io_ctx_col_type",
        "wirelog_io_ctx_param",
        "wirelog_io_ctx_intern_string",
        "wirelog_io_ctx_platform",
        "wirelog_io_ctx_set_platform",
    ]
    for name in names:
        fn = getattr(LIB, name)
        assert fn.argtypes is not None, f"{name} has no argtypes"


def test_abi_version_constant_is_two():
    """wirelog 0.40+ requires ABI version 2; 0.30 (version 1) is rejected."""
    assert WIRELOG_IO_ABI_VERSION == 2


def test_register_invalid_abi_returns_minus_one():
    """An adapter struct with the wrong abi_version is rejected and
    `wirelog_io_last_error` carries a diagnostic. The read / validate
    fields must be valid CFUNCTYPE instances even for the failure
    test — ctypes refuses to assign Python `None` to a function-pointer
    field; build no-op stubs."""
    read_field_type, validate_field_type = (
        IOAdapterStruct._fields_[3][1],
        IOAdapterStruct._fields_[4][1],
    )

    @read_field_type
    def _noop_read(ctx, out_data, out_n, user_data):  # pragma: no cover
        return 0

    @validate_field_type
    def _noop_validate(ctx, errbuf, errlen, user_data):  # pragma: no cover
        return 0

    adapter = IOAdapterStruct(
        abi_version=1,  # too-old version
        scheme=b"_pytest_bad_abi",
        description=b"intentionally bad",
        read=_noop_read,
        validate=_noop_validate,
        user_data=None,
    )
    rc = LIB.wirelog_io_register_adapter(ctypes.byref(adapter))
    assert rc == -1
    err = LIB.wirelog_io_last_error()
    assert err is not None and err  # non-empty error text


def test_find_unknown_scheme_returns_null():
    ptr = LIB.wirelog_io_find_adapter(b"_pytest_no_such_scheme_xyz")
    assert not ptr


def test_unregister_unknown_scheme_returns_minus_one():
    rc = LIB.wirelog_io_unregister_adapter(b"_pytest_no_such_scheme_xyz")
    assert rc == -1
