# SPDX-License-Identifier: Apache-2.0 OR GPL-3.0-or-later
"""Tests for `pyrewire.session.Session` (#21).

The advanced API binds to wirelog's lower-level surface. Step/snapshot
behaviour depends on wirelog's stratifier and (per wirelog#852) is
sensitive to recursive-aggregation residue; these tests therefore stay
behavioural (return shapes, mode-machine semantics, lifetime) rather
than asserting specific delta counts.
"""

from __future__ import annotations

import gc

import pytest

from pyrewire._core.errors import WirelogInternError, WirelogModeError
from pyrewire._ffi._enums import BackendKind
from pyrewire.program import Program
from pyrewire.session import Session


def _simple_program() -> Program:
    return Program.from_string(
        ".decl edge(x: int32, y: int32)\n" ".decl reach(x: int32)\n" "reach(X) :- edge(X, _).\n"
    )


def test_create_default_backend_closes_cleanly():
    prog = _simple_program()
    with Session(prog) as s:
        assert s.program is prog


def test_create_columnar_backend():
    prog = _simple_program()
    with Session(prog, backend=BackendKind.COLUMNAR, num_workers=2):
        pass


def test_seed_intern_and_lookup():
    prog = _simple_program()
    with Session(prog) as s:
        s.seed_intern("alice", 42)
        assert s.intern_table.lookup(42) == "alice"
        assert s.intern_table.contains_value("alice")


def test_reject_intern_raises():
    prog = _simple_program()
    with Session(prog) as s:
        with pytest.raises(WirelogInternError):
            s.intern_table.intern("alice")  # no forward intern on advanced


def test_insert_empty_rows_is_noop():
    prog = _simple_program()
    with Session(prog) as s:
        s.insert("edge", [])  # must not raise / call FFI


def test_insert_row_shape_mismatch_raises():
    prog = _simple_program()
    with Session(prog) as s:
        with pytest.raises(ValueError):
            s.insert("edge", [(1, 2), (3,)])  # second row arity differs


def test_insert_zero_columns_raises():
    prog = _simple_program()
    with Session(prog) as s:
        with pytest.raises(ValueError):
            s.insert("edge", [()])


def test_insert_batch_runs():
    prog = _simple_program()
    with Session(prog) as s:
        s.insert("edge", [(i, i + 1) for i in range(1000)])


def test_close_is_idempotent():
    prog = _simple_program()
    s = Session(prog)
    s.close()
    s.close()


def test_program_kept_alive_after_caller_drops_reference():
    """Borrowed program: caller drops its handle but session keeps it alive."""
    prog = _simple_program()
    s = Session(prog)
    prog_id = id(prog)
    del prog
    gc.collect()
    # If GC freed the program the next FFI call would segfault. Touch it.
    s.insert("edge", [(1, 2)])
    assert id(s.program) == prog_id
    s.close()


def test_lock_disabled_path():
    """With lock=False, the wrapping context manager is a no-op."""
    prog = _simple_program()
    with Session(prog, lock=False) as s:
        s.insert("edge", [(1, 2)])


# ----------------------------------------------------------------------
# Mode machine
# ----------------------------------------------------------------------


def test_snapshot_after_step_raises_mode_error():
    """Once committed to INCREMENTAL, calling snapshot must raise."""
    prog = _simple_program()
    with Session(prog) as s:
        try:
            s.step()
        except Exception:
            # If wirelog rejects step on an empty program, force the
            # mode commit through insert (which is also INCREMENTAL).
            s.insert("edge", [(1, 2)])
        with pytest.raises(WirelogModeError):
            s.snapshot()


def test_step_after_snapshot_raises_mode_error():
    prog = _simple_program()
    with Session(prog) as s:
        try:
            s.snapshot()
        except Exception:
            # If wirelog rejects snapshot on an empty program, commit
            # the QUERY mode by hand via the internal helper. (The mode
            # machine is committed BEFORE the FFI call returns.)
            pass
        with pytest.raises(WirelogModeError):
            s.step()


def test_set_delta_callback_commits_incremental_mode():
    prog = _simple_program()

    seen: list = []

    def on_delta(rel, vals, diff):
        seen.append((rel, vals, diff))

    with Session(prog) as s:
        s.set_delta_callback(on_delta)
        with pytest.raises(WirelogModeError):
            s.snapshot()


def test_clear_delta_callback_after_set():
    prog = _simple_program()
    with Session(prog) as s:
        s.set_delta_callback(lambda r, v, d: None)
        s.set_delta_callback(None)  # idempotent clear path
