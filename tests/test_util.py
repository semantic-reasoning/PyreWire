# SPDX-License-Identifier: Apache-2.0 OR GPL-3.0-or-later
"""Tests for `pyrewire._ffi._util`."""

from __future__ import annotations

import re

from pyrewire._ffi._enums import AggFn, ArithOp, CmpOp
from pyrewire._ffi._util import (
    agg_fn_name,
    arith_op_name,
    build_config,
    cmp_op_name,
    wirelog_version,
)


def test_wirelog_version_returns_dotted_string():
    s = wirelog_version()
    assert isinstance(s, str)
    # Either reported by libwirelog or falls back to pyrewire.__version__;
    # both must match the dotted-version pattern.
    assert re.match(r"^\d+\.\d+", s), f"unexpected version string {s!r}"


def test_build_config_shape():
    cfg = build_config()
    assert set(cfg.keys()) == {"embedded", "ipc", "threads"}
    for value in cfg.values():
        assert value is None or isinstance(value, bool)


def test_cmp_op_names_cover_every_member():
    for op in CmpOp:
        name = cmp_op_name(op)
        assert isinstance(name, str) and name


def test_arith_op_names_cover_every_member():
    for op in ArithOp:
        name = arith_op_name(op)
        assert isinstance(name, str) and name


def test_agg_fn_names_cover_every_member():
    for fn in AggFn:
        name = agg_fn_name(fn)
        assert isinstance(name, str) and name


def test_cmp_op_name_accepts_raw_int():
    # int(CmpOp.EQ) should produce the same text as CmpOp.EQ.
    assert cmp_op_name(int(CmpOp.EQ)) == cmp_op_name(CmpOp.EQ)


def test_unknown_op_does_not_raise():
    """Unknown op codes either get the libwirelog placeholder (e.g. '?')
    or the PyreWire-side synthetic text. The contract is 'returns a
    non-empty string, never raises'."""
    s = cmp_op_name(999)
    assert isinstance(s, str)
    assert s  # non-empty
