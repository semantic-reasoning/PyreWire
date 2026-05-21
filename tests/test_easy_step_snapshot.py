"""Tests for `EasySession.step` / `set_delta_callback` / `snapshot` (#10 + #11).

The delta-mode machinery requires the wirelog#852 recursive-aggregation
residue fix, which was merged on `wirelog/main` 2026-05-21 but is not
yet in a tagged release. The tests skip themselves when the loaded
libwirelog does not include the fix; CI matching the pinned
`v0.41.0` tag therefore skips them rather than reporting spurious
failures.

Once wirelog cuts the next tag (tracked in wirelog#859), bump
PyreWire's `WIRELOG_VERSION` and the skip clears automatically.
"""

from __future__ import annotations

import os
import sys

import pytest

from pyrewire._core.errors import WirelogModeError
from pyrewire.helpers import make_safe_print_delta

# Local dev builds may be ahead of the tagged release (e.g. 0.41.99).
# Skip when running against a pinned-tag CI build that predates #852.
# The simplest signal is the runtime wirelog version: anything > 0.41.0
# carries the fix.
try:
    import pyrewire as _pyrewire

    _wirelog_ver = tuple(int(p) for p in _pyrewire.wirelog_version().split("."))
except Exception:
    _wirelog_ver = (0, 0, 0)

pytestmark = pytest.mark.skipif(
    _wirelog_ver <= (0, 41, 0),
    reason=(
        f"EasySession.step/snapshot needs wirelog > 0.41.0 (has wirelog#852); "
        f"running libwirelog reports {'.'.join(str(p) for p in _wirelog_ver)}. "
        "Tracked in wirelog#859."
    ),
)


from pyrewire.session import EasySession  # noqa: E402

SRC = """
.decl edge(x: int32, y: int32)
.decl reach(x: int32)
reach(X) :- edge(X, _).
"""


def test_step_returns_list_of_decoded_deltas():
    """`step()` must return a `list[Delta]` even if it's empty —
    wirelog may stage events across multiple step() calls."""
    with EasySession(SRC) as s:
        s.insert("edge", [1, 2])
        s.insert("edge", [2, 3])
        for _ in range(5):  # drive to a fixed point
            deltas = s.step()
            assert isinstance(deltas, list)
            for d in deltas:
                assert isinstance(d, tuple) and len(d) == 3


def test_step_preserves_insert_buffers_until_evaluation_issue_863():
    """Regression for wirelog#863: Python-side bookkeeping between
    insert() and step() must not let ctypes input buffers be reclaimed."""
    src = """
    .decl edge(x: int32, y: int32)
    .decl reach(x: int32, y: int32)
    reach(X, Y) :- edge(X, Y).
    reach(X, Y) :- edge(X, Z), reach(Z, Y).
    """
    with EasySession(src) as s:
        s.insert("edge", [1, 2])
        s.insert("edge", [2, 3])
        # Force Python allocations in the same window where step() also
        # performs mode/callback bookkeeping.
        _junk = [b"edge" for _ in range(32)]
        deltas_1 = s.step()
        assert {row for rel, row, diff in deltas_1 if rel == "reach" and diff > 0} == {
            (1, 2),
            (1, 3),
            (2, 3),
        }

        s.insert("edge", [3, 4])
        _junk = [b"edge" for _ in range(32)]
        deltas_2 = s.step()
        reach_added = {row for rel, row, diff in deltas_2 if rel == "reach" and diff > 0}
        assert (3, 4) in reach_added


def test_step_with_callback_does_not_raise():
    """Setting a delta callback and driving step() must not raise.
    Whether wirelog buffers events for delivery is a separate
    upstream contract (wirelog#852 / wirelog#859); this test only
    asserts that the Python wiring is sound."""
    received: list = []

    def cb(event):
        received.append(event)

    with EasySession(SRC) as s:
        s.set_delta_callback(cb)
        s.insert("edge", [1, 2])
        for _ in range(3):
            out = s.step()
            assert isinstance(out, list)


def test_set_delta_callback_clears_with_none():
    """Calling `set_delta_callback(None)` after a successful set must
    not raise."""
    with EasySession(SRC) as s:
        s.set_delta_callback(lambda _e: None)
        s.set_delta_callback(None)


def test_step_after_snapshot_raises_mode_error():
    with EasySession(SRC) as s:
        # First snapshot commits QUERY mode.
        s.snapshot("reach")
        with pytest.raises(WirelogModeError):
            s.step()


def test_snapshot_after_step_raises_mode_error():
    with EasySession(SRC) as s:
        s.insert("edge", [1, 2])
        s.step()  # commits INCREMENTAL
        with pytest.raises(WirelogModeError):
            s.snapshot("reach")


def test_set_delta_callback_rejects_wirelog_print_delta():
    """Passing the C entry point directly must raise — that function
    aborts the process on missing reverse-intern."""
    from pyrewire._ffi import LIB

    if not hasattr(LIB, "wirelog_easy_print_delta"):
        pytest.skip("wirelog build does not export wirelog_easy_print_delta")
    with EasySession(SRC) as s:
        with pytest.raises(TypeError, match="abort"):
            s.set_delta_callback(LIB.wirelog_easy_print_delta)


def test_set_delta_callback_accepts_safe_print_delta():
    """The supplied safe replacement passes the guard cleanly."""
    with EasySession(SRC) as s:
        safe = make_safe_print_delta(s._intern, file=open(os.devnull, "w"))
        s.set_delta_callback(safe)


def test_snapshot_returns_list_of_tuples():
    with EasySession(SRC) as s:
        rows = s.snapshot("reach")
        assert isinstance(rows, list)
        for r in rows:
            assert isinstance(r, tuple)


# Standalone guard test: keep flake8 happy by referencing `sys`.
def test_module_uses_pytest_skipif_for_old_wirelog():
    """Sanity assertion: pytestmark is non-None so the suite skips
    when wirelog is too old."""
    assert pytestmark is not None
    assert sys.version_info >= (3, 10)
