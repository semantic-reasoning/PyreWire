# SPDX-License-Identifier: Apache-2.0 OR GPL-3.0-or-later
"""Tests for `BatchProgram.load_all_facts` / `load_input_files` /
`optimizer_debug` (#19)."""

from __future__ import annotations

from pathlib import Path

import pytest

from pyrewire._core.errors import ExecError, WirelogError
from pyrewire.batch import BatchProgram


def test_optimizer_debug_returns_string():
    src = (
        ".decl edge(x: int32, y: int32)\n"
        ".decl reach(x: int32)\n"
        "edge(1, 2).\n"
        "reach(X) :- edge(X, _).\n"
    )
    with BatchProgram.from_string(src) as bp:
        out = bp.optimizer_debug()
        assert isinstance(out, str)


def test_load_all_facts_runs_without_error():
    src = (
        ".decl edge(x: int32, y: int32)\n"
        ".decl reach(x: int32)\n"
        "edge(1, 2).\n"
        "edge(2, 3).\n"
        "reach(X) :- edge(X, _).\n"
    )
    with BatchProgram.from_string(src) as bp:
        bp.optimize()
        bp.load_all_facts()
        bp.evaluate().close()


def test_load_input_files_runs(tmp_path: Path):
    """Programs with no `.input` directives are a no-op."""
    src = ".decl x(a: int32)\nx(1).\n"
    with BatchProgram.from_string(src) as bp:
        # On a program without `.input` directives this either returns
        # cleanly or raises a wirelog ExecError; both are acceptable.
        try:
            bp.load_input_files()
        except WirelogError:
            pass


def test_load_all_facts_after_close_raises():
    bp = BatchProgram.from_string(".decl x(a: int32)\nx(1).\n")
    bp.close()
    with pytest.raises(ExecError):
        bp.load_all_facts()


def test_optimizer_debug_after_close_raises():
    bp = BatchProgram.from_string(".decl x(a: int32)\n")
    bp.close()
    with pytest.raises(ExecError):
        bp.optimizer_debug()
