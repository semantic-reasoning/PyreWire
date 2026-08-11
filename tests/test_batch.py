# SPDX-License-Identifier: Apache-2.0 OR GPL-3.0-or-later
"""Tests for `pyrewire.batch.BatchProgram` and `Result` (#17 + #18)."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from pyrewire._core.errors import ExecError
from pyrewire._ffi._loader import _parse_version, _pep440_base
from pyrewire._ffi._util import wirelog_version
from pyrewire.batch import BatchProgram, Result

# ----------------------------------------------------------------------
# BatchProgram (#17)
# ----------------------------------------------------------------------


def test_from_string_optimize_evaluate():
    src = """
    .decl edge(x: int32, y: int32)
    .decl reach(x: int32)
    edge(1, 2).
    edge(2, 3).
    reach(X) :- edge(X, _).
    """
    with BatchProgram.from_string(src) as bp:
        bp.optimize()
        res = bp.evaluate()
        try:
            assert isinstance(res, Result)
        finally:
            res.close()


def test_from_file_parses(tmp_path: Path):
    p = tmp_path / "tiny.dl"
    p.write_text(".decl edge(x: int32, y: int32)\n" "edge(1, 2).\n" "edge(2, 3).\n")
    with BatchProgram.from_file(p) as bp:
        bp.optimize()
        bp.evaluate().close()


def test_close_is_idempotent():
    bp = BatchProgram.from_string(".decl x(a: int32)\n")
    bp.close()
    bp.close()  # second call must be a no-op


def test_call_after_close_raises():
    bp = BatchProgram.from_string(".decl x(a: int32)\n")
    bp.close()
    with pytest.raises(ExecError):
        bp.optimize()


def test_evaluate_without_optimize_is_allowed():
    """`optimize()` is optional — `evaluate` still produces a result."""
    with BatchProgram.from_string(".decl x(a: int32)\nx(1).\n") as bp:
        res = bp.evaluate()
        res.close()


# A rule with four or more body atoms lets SIP insert a semijoin with
# something resolved above it. Before wirelog#955 the semijoin widened the
# reported output layout by the right relation's arity, shifting every
# column resolved above it; the out-of-range lookup then fell back to
# column 0, so the last head variable silently came back as 0 (#180).
#
# The corruption is silent — `evaluate()` succeeds and returns the right
# row count and arity — so this compares the optimized result against the
# unoptimized one instead of just asserting evaluation worked.
_SEMIJOIN_LAYOUT_SRC = """
.decl typ(s: int32, c: int32)
.decl mand(c: int32)
.decl ord(s: int32, o: int32)
.decl rsn(s: int32, r: int32)
.decl out(o: int32, s: int32, r: int32)

out(O, S, R) :- mand(C), typ(S, C), ord(S, O), rsn(S, R).

typ(1, 5).
mand(5).
ord(1, 10).
rsn(1, 7).
"""


def _semijoin_layout_rows(optimize: bool) -> list[tuple[int, ...]]:
    with BatchProgram.from_string(_SEMIJOIN_LAYOUT_SRC) as bp:
        if optimize:
            bp.optimize()
        bp.load_all_facts()
        res = bp.evaluate()
        try:
            return sorted({tuple(int(v) for v in row) for row in res.relation("out")})
        finally:
            res.close()


def _wirelog_older_than(minimum: tuple[int, int, int]) -> bool:
    return _parse_version(_pep440_base(wirelog_version())) < minimum


@pytest.mark.skipif(
    _wirelog_older_than((0, 54, 0)),
    reason=(
        "wirelog#955 (the #180 fix) first ships in wirelog 0.54.0; the "
        "loader floor still admits 0.52.0, where this corrupts silently."
    ),
)
def test_optimize_preserves_head_bindings_with_four_body_atoms():
    """`optimize()` must not change the answer (#180, wirelog#955)."""
    optimized = _semijoin_layout_rows(optimize=True)

    assert optimized == _semijoin_layout_rows(optimize=False)
    assert optimized == [(10, 1, 7)]


# ----------------------------------------------------------------------
# Result (#18)
# ----------------------------------------------------------------------


def _build_reach_result() -> tuple[BatchProgram, Result]:
    src = """
    .decl edge(x: int32, y: int32)
    .decl reach(x: int32)
    edge(1, 2).
    edge(2, 3).
    reach(X) :- edge(X, _).
    """
    bp = BatchProgram.from_string(src)
    bp.optimize()
    return bp, bp.evaluate()


def test_cardinality_returns_int():
    bp, res = _build_reach_result()
    try:
        n = res.cardinality("reach")
        assert isinstance(n, int)
        assert n >= 0
    finally:
        res.close()
        bp.close()


def test_relation_decodes_ints():
    bp, res = _build_reach_result()
    try:
        # `reach` is derived (IDB) — batch result exposes IDB rows.
        rows = res.relation("reach")
        assert rows  # rule produces facts
        assert all(isinstance(c, int) for r in rows for c in r)
    finally:
        res.close()
        bp.close()


def test_write_csv_roundtrip(tmp_path: Path):
    bp, res = _build_reach_result()
    try:
        out = tmp_path / "reach.csv"
        res.write_csv("reach", out)
        rows = list(csv.reader(out.open()))
        assert res.cardinality("reach") == len(rows)
    finally:
        res.close()
        bp.close()


def test_relation_iter_matches_relation():
    bp, res = _build_reach_result()
    try:
        a = res.relation("reach")
        b = list(res.relation_iter("reach"))
        assert a == b
    finally:
        res.close()
        bp.close()


def test_write_csv_unexported_relation_raises(tmp_path: Path):
    """EDB-only relations are not in the batch result; `write_csv` must
    surface the underlying ExecError rather than silently writing nothing."""
    bp, res = _build_reach_result()
    try:
        with pytest.raises(ExecError):
            res.write_csv("edge", tmp_path / "edge.csv")
    finally:
        res.close()
        bp.close()


def test_close_after_program_close_ok():
    bp, res = _build_reach_result()
    res.close()
    bp.close()  # closing program AFTER result must not raise


def test_call_after_result_close_raises():
    bp, res = _build_reach_result()
    res.close()
    with pytest.raises(ExecError):
        res.cardinality("edge")
    bp.close()


def test_relation_returns_empty_for_unknown_relation(tmp_path: Path):
    """An unknown relation has cardinality 0 and an empty CSV."""
    with BatchProgram.from_string(".decl x(a: int32)\n") as bp:
        res = bp.evaluate()
        try:
            assert res.cardinality("does_not_exist") == 0
        finally:
            res.close()
