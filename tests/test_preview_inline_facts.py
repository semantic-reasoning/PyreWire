"""Tests for `preview_inline_facts` and `insert_with_dedupe` (#47)."""

from __future__ import annotations

from pyrewire._ffi._enums import BackendKind
from pyrewire.program import Program
from pyrewire.session import EasySession, Session


def test_easy_preview_inline_facts_empty_when_no_inline_facts():
    src = ".decl edge(x: int32, y: int32)\n"
    with EasySession(src) as s:
        assert s.preview_inline_facts("edge") == []


def test_easy_preview_inline_facts_returns_inline_rows():
    src = ".decl edge(x: int32, y: int32)\n" "edge(1, 2).\n" "edge(2, 3).\n"
    with EasySession(src) as s:
        rows = s.preview_inline_facts("edge")
        assert (1, 2) in rows
        assert (2, 3) in rows


def test_easy_preview_inline_facts_unknown_relation_returns_empty():
    src = ".decl x(a: int32)\n"
    with EasySession(src) as s:
        assert s.preview_inline_facts("does_not_exist") == []


def test_easy_insert_with_dedupe_skips_duplicate():
    """`insert_with_dedupe` returns False for an inline-fact duplicate."""
    src = ".decl edge(x: int32, y: int32)\n" "edge(1, 2).\n"
    with EasySession(src) as s:
        # `edge(1, 2)` is already in the EDB — duplicate insert would
        # raise the multiplicity to +2.
        inserted = s.insert_with_dedupe("edge", [1, 2])
        assert inserted is False


def test_easy_insert_with_dedupe_inserts_new_row():
    src = ".decl edge(x: int32, y: int32)\n" "edge(1, 2).\n"
    with EasySession(src) as s:
        inserted = s.insert_with_dedupe("edge", [3, 4])
        assert inserted is True


def test_easy_preview_resists_invalid_dl_source():
    """If the side-program parse fails, the helper returns []."""
    # An invalid program raises ParseError at construction. But since
    # EasySession may still accept it (wirelog's easy facade has its
    # own parser), we instead simulate by monkeypatching the schema
    # program to None.
    src = ".decl edge(x: int32, y: int32)\n"
    with EasySession(src) as s:
        s._schema_program = None  # simulate failed side parse
        assert s.preview_inline_facts("edge") == []


# ----------------------------------------------------------------------
# Session (advanced)
# ----------------------------------------------------------------------


def test_session_preview_inline_facts_returns_program_rows():
    prog = Program.from_string(".decl edge(x: int32, y: int32)\n" "edge(1, 2).\n" "edge(2, 3).\n")
    with Session(prog, backend=BackendKind.DEFAULT) as s:
        rows = s.preview_inline_facts("edge")
        assert (1, 2) in rows
        assert (2, 3) in rows


def test_session_preview_inline_facts_unknown_relation_returns_empty():
    prog = Program.from_string(".decl x(a: int32)\n")
    with Session(prog) as s:
        assert s.preview_inline_facts("does_not_exist") == []
