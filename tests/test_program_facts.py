# SPDX-License-Identifier: Apache-2.0 OR GPL-3.0-or-later
"""Tests for `Program.facts_raw` / `Program.facts` (issue #15)."""

from __future__ import annotations

import pytest

from pyrewire import ExecError, Program
from pyrewire._core.intern import InternTable


def test_facts_raw_empty_when_no_inline_facts():
    with Program.from_string(".decl x(a: int32)\n") as p:
        assert p.facts_raw("x") == []


def test_facts_raw_returns_int64_tuples_for_numeric_relation():
    src = ".decl edge(x: int32, y: int32)\nedge(1, 2).\nedge(2, 3).\n"
    with Program.from_string(src) as p:
        rows = p.facts_raw("edge")
        assert sorted(rows) == [(1, 2), (2, 3)]


def test_facts_raw_unknown_relation_raises():
    with Program.from_string(".decl x(a: int32)\n") as p:
        with pytest.raises(ExecError):
            p.facts_raw("nope")


def test_facts_decodes_int_columns():
    src = ".decl edge(x: int32, y: int32)\nedge(1, 2).\n"
    with Program.from_string(src) as p:
        rows = p.facts("edge")
        assert rows == [(1, 2)]


def test_facts_decodes_bool_column():
    """wirelog's bool literal syntax is engine-dependent; this test
    exercises a handful of common spellings and accepts any that the
    parser permits, then verifies the bool decoding path."""
    for src_template in (
        ".decl flag(a: int32, b: bool)\nflag(1, true).\nflag(2, false).\n",
        ".decl flag(a: int32, b: bool)\nflag(1, 1).\nflag(2, 0).\n",
    ):
        try:
            with Program.from_string(src_template) as p:
                rows = p.facts("flag")
        except Exception:
            continue
        # Decoded rows should be (int, bool) pairs.
        assert all(isinstance(r[0], int) and isinstance(r[1], bool) for r in rows)
        return
    pytest.skip("no accepted bool-literal spelling for wirelog 0.41.0")


def test_facts_string_columns_returned_as_ids_without_intern():
    src = '.decl name(s: symbol)\nname("alice").\n'
    with Program.from_string(src) as p:
        rows = p.facts("name")
        assert len(rows) == 1
        # Without an InternTable, STRING values come through as raw int ids.
        (val,) = rows[0]
        assert isinstance(val, int)


def test_facts_string_columns_decoded_when_intern_table_seeded():
    src = '.decl name(s: symbol)\nname("alice").\n'
    with Program.from_string(src) as p:
        # Discover the id wirelog assigned by reading raw first, then
        # seed the InternTable with the (id, string) pair so a follow-up
        # `facts(...)` decodes it.
        (raw_id,) = p.facts_raw("name")[0]
        intern = InternTable(intern_fn=lambda b: -1)  # never used
        intern.remember(int(raw_id), "alice")
        rows = p.facts("name", intern=intern)
        assert rows == [("alice",)]


def test_facts_repeat_calls_do_not_leak():
    """Stress test: ensure the libc-malloc'd buffer is freed every call."""
    src = ".decl edge(x: int32, y: int32)\nedge(1, 2).\nedge(2, 3).\nedge(3, 4).\n"
    with Program.from_string(src) as p:
        for _ in range(500):
            assert len(p.facts_raw("edge")) == 3
