# SPDX-License-Identifier: Apache-2.0 OR GPL-3.0-or-later
"""Tests for `EasySession._schema_for` and the schema cache (#43)."""

from __future__ import annotations

import pytest

from pyrewire._core.errors import ExecError
from pyrewire._ffi._enums import ColumnType
from pyrewire.session import EasySession


def test_schema_for_returns_schema_for_declared_relation():
    src = ".decl edge(x: int32, y: int32)\n"
    with EasySession(src) as s:
        sch = s._schema_for("edge")
        assert sch.relation == "edge"
        assert len(sch.columns) == 2
        assert sch.columns[0].type == ColumnType.INT32


def test_schema_for_caches_after_first_lookup():
    src = ".decl edge(x: int32, y: int32)\n"
    with EasySession(src) as s:
        first = s._schema_for("edge")
        second = s._schema_for("edge")
        # Cache hit returns the same Schema instance.
        assert first is second
        assert "edge" in s._schema_cache


def test_schema_for_unknown_relation_raises_exec_error():
    src = ".decl edge(x: int32, y: int32)\n"
    with EasySession(src) as s:
        with pytest.raises(ExecError, match="no schema for relation"):
            s._schema_for("does_not_exist")


def test_schema_for_after_close_raises():
    src = ".decl edge(x: int32, y: int32)\n"
    s = EasySession(src)
    s.close()
    with pytest.raises(ExecError, match="schema cache is closed"):
        s._schema_for("edge")


def test_schema_cache_cleared_on_close():
    src = ".decl edge(x: int32, y: int32)\n"
    s = EasySession(src)
    s._schema_for("edge")
    assert "edge" in s._schema_cache
    s.close()
    assert s._schema_cache == {}


def test_schema_for_handles_multiple_relations():
    src = ".decl a(x: int32)\n.decl b(y: int64)\n.decl c(z: symbol)\n"
    with EasySession(src) as s:
        s._schema_for("a")
        s._schema_for("b")
        s._schema_for("c")
        assert set(s._schema_cache) == {"a", "b", "c"}
        # All three have distinct column types.
        assert s._schema_cache["a"].columns[0].type == ColumnType.INT32
        assert s._schema_cache["b"].columns[0].type == ColumnType.INT64
        assert s._schema_cache["c"].columns[0].type == ColumnType.STRING
