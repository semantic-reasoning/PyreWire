# SPDX-License-Identifier: Apache-2.0 OR GPL-3.0-or-later
"""Tests for `pyrewire.Program` and its dataclass companions."""

from __future__ import annotations

from pathlib import Path

import pytest

from pyrewire import ColumnType, ParseError, Program


def test_from_string_minimal_program():
    with Program.from_string(".decl x(a: int32)\n") as p:
        assert isinstance(p.rule_count(), int)


def test_from_string_invalid_raises_parse_error():
    with pytest.raises(ParseError):
        Program.from_string("this is not datalog at all")


def test_from_file_parse_error_carries_location(tmp_path: Path):
    bad = tmp_path / "bad.dl"
    bad.write_text(".garbage\n")
    with pytest.raises(ParseError) as excinfo:
        Program.from_file(bad)
    # parse_with_error_info may populate line/column; both fields are
    # optional, so just assert the ParseError type and the message exists.
    assert str(excinfo.value)


def test_schema_columns_match_decl():
    src = ".decl edge(x: int32, y: symbol)\n"
    with Program.from_string(src) as p:
        sch = p.schema("edge")
        assert sch is not None
        assert sch.relation == "edge"
        assert len(sch.columns) == 2
        assert sch.columns[0].name == "x"
        assert sch.columns[0].type == ColumnType.INT32
        assert sch.columns[1].name == "y"
        assert sch.columns[1].type == ColumnType.STRING


def test_schema_unknown_relation_returns_none():
    with Program.from_string(".decl x(a: int32)\n") as p:
        assert p.schema("nope") is None


def test_stratum_iteration_works_for_recursive_program():
    src = (
        ".decl edge(x: int32, y: int32)\n"
        ".decl r(x: int32, y: int32)\n"
        "r(X, Y) :- edge(X, Y).\n"
        "r(X, Z) :- r(X, Y), edge(Y, Z).\n"
    )
    with Program.from_string(src) as p:
        assert p.stratum_count() >= 1
        strata = list(p.strata())
        assert len(strata) == p.stratum_count()
        # The recursive rule should land in a stratum flagged recursive.
        assert any(s.is_recursive for s in strata)


def test_rule_count_matches_source():
    src = ".decl a(x: int32)\n.decl b(x: int32)\nb(X) :- a(X).\n"
    with Program.from_string(src) as p:
        assert p.rule_count() == 1


def test_is_stratified_positive_case():
    src = ".decl a(x: int32)\n.decl b(x: int32)\nb(X) :- a(X).\n"
    with Program.from_string(src) as p:
        assert p.is_stratified()


def test_close_idempotent():
    p = Program.from_string(".decl x(a: int32)\n")
    p.close()
    p.close()


def test_repr_smoke():
    with Program.from_string(".decl x(a: int32)\n") as p:
        assert "Program" in repr(p)
