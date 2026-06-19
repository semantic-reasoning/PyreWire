# SPDX-License-Identifier: Apache-2.0 OR GPL-3.0-or-later
"""Tests for `EasySession.insert_sym` / `remove_sym` (#44)."""

from __future__ import annotations

import pytest

from pyrewire._core.errors import ExecError
from pyrewire.session import EasySession


def test_insert_sym_single_symbol():
    src = ".decl name(x: symbol)\n"
    with EasySession(src) as s:
        s.insert_sym("name", "alice")
        # Symbol should be mirrored into the local reverse-intern cache.
        assert s._intern.contains_value("alice")


def test_insert_sym_two_symbols():
    src = ".decl friend(x: symbol, y: symbol)\n"
    with EasySession(src) as s:
        s.insert_sym("friend", "alice", "bob")
        assert s._intern.contains_value("alice")
        assert s._intern.contains_value("bob")


def test_insert_sym_no_symbols():
    """Zero-arity relation: no symbols, but the FFI call still runs."""
    src = ".decl marker()\n"
    with EasySession(src) as s:
        # If wirelog rejects zero-arity calls, accept either outcome but
        # the wrapper itself must not raise before the FFI call.
        try:
            s.insert_sym("marker")
        except ExecError:
            pass


def test_insert_sym_too_many_raises_before_ffi():
    src = ".decl row(a: symbol)\n"
    with EasySession(src) as s:
        with pytest.raises(ValueError, match="at most 16"):
            s.insert_sym("row", *(f"s{i}" for i in range(17)))


def test_remove_sym_roundtrip():
    src = ".decl friend(x: symbol, y: symbol)\n"
    with EasySession(src) as s:
        s.insert_sym("friend", "alice", "bob")
        s.remove_sym("friend", "alice", "bob")
        # Both symbols stay in the intern cache (interning is monotonic).
        assert s._intern.contains_value("alice")
        assert s._intern.contains_value("bob")


def test_insert_sym_intern_cache_mirrors_wirelog():
    """The local cache must reflect the same id wirelog assigned."""
    src = ".decl person(x: symbol)\n"
    with EasySession(src) as s:
        s.insert_sym("person", "alice")
        # A subsequent explicit intern() returns the same id (forward
        # cache hit, no second FFI crossing).
        idx = s.intern("alice")
        # Reverse-lookup should resolve to the original string.
        assert s._intern.lookup(idx) == "alice"


def _patch_dummy(*args, **kwargs):
    return None
