"""Tests for `Session.insert_batch` / `remove_batch` (#22)."""

from __future__ import annotations

import pytest

import pyrewire.session as session_mod
from pyrewire.program import Program
from pyrewire.session import Session

np = pytest.importorskip("numpy")


def _simple_program() -> Program:
    return Program.from_string(".decl edge(x: int32, y: int32)\n")


def test_insert_int64_ndarray_zero_copy():
    arr = np.arange(20, dtype=np.int64).reshape(10, 2)
    prog = _simple_program()
    with Session(prog) as s:
        s.insert_batch("edge", arr)


def test_insert_int32_coerces_to_int64():
    arr = np.arange(20, dtype=np.int32).reshape(10, 2)
    prog = _simple_program()
    with Session(prog) as s:
        s.insert_batch("edge", arr)
    # The original array's dtype must NOT have been mutated.
    assert arr.dtype == np.int32


def test_insert_non_contiguous_array():
    """A non-contiguous view triggers an internal `ascontiguousarray`
    copy; the wirelog call must still succeed."""
    base = np.arange(40, dtype=np.int64).reshape(10, 4)
    view = base[:, ::2]  # non-contiguous 10x2 view
    assert not view.flags["C_CONTIGUOUS"]
    prog = _simple_program()
    with Session(prog) as s:
        s.insert_batch("edge", view)


def test_insert_rejects_1d_array():
    arr = np.arange(10, dtype=np.int64)
    prog = _simple_program()
    with Session(prog) as s:
        with pytest.raises(ValueError):
            s.insert_batch("edge", arr)


def test_insert_empty_ndarray_is_noop():
    arr = np.zeros((0, 2), dtype=np.int64)
    prog = _simple_program()
    with Session(prog) as s:
        s.insert_batch("edge", arr)


def test_remove_batch_ndarray():
    arr = np.array([[1, 2], [3, 4]], dtype=np.int64)
    prog = _simple_program()
    with Session(prog) as s:
        s.insert_batch("edge", arr)
        s.remove_batch("edge", arr)


def test_insert_batch_list_fallback():
    """Plain `list[list[int]]` still works through the fallback path."""
    prog = _simple_program()
    with Session(prog) as s:
        s.insert_batch("edge", [(1, 2), (3, 4), (5, 6)])


def test_insert_batch_fallback_without_numpy(monkeypatch):
    """Simulate a NumPy-less install via monkeypatch — the list path
    still has to work."""
    monkeypatch.setattr(session_mod, "_np", None)
    prog = _simple_program()
    with Session(prog) as s:
        s.insert_batch("edge", [(1, 2), (3, 4)])


def test_insert_batch_empty_list_is_noop():
    prog = _simple_program()
    with Session(prog) as s:
        s.insert_batch("edge", [])
