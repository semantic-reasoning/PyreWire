"""Integration test mirroring wirelog `examples/09-retraction-basics` (#12).

Drives `EasySession.step()` through the three retraction phases:

1. Insert symmetric friendship → derived `mutual` rows appear.
2. Insert an unrelated edge → no new `mutual` rows.
3. Retract one direction → `mutual` rows retract symmetrically.

Skips when the loaded `libwirelog` is `<= 0.41.0` because the
delta-mode machinery depends on wirelog#852 (tracked in wirelog#859).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


def _wirelog_ver() -> tuple[int, ...]:
    try:
        import pyrewire

        return tuple(int(p) for p in pyrewire.wirelog_version().split("."))
    except Exception:  # noqa: BLE001
        return (0, 0, 0)


pytestmark = pytest.mark.skipif(
    _wirelog_ver() <= (0, 41, 0),
    reason=(
        "Retraction test needs wirelog > 0.41.0 (wirelog#852); "
        "running libwirelog is older. Tracked in wirelog#859."
    ),
)


def _import_example() -> object:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    from examples.retraction_basics import run  # noqa: WPS433

    return run


def test_retraction_basics_runs_through_three_phases():
    """The example's `run()` must return all three phases as lists of
    tuples."""
    run = _import_example()
    phases = run()  # type: ignore[operator]
    assert set(phases) == {
        "phase1_mutual_emerges",
        "phase2_no_new_mutual",
        "phase3_retraction",
    }
    for label, deltas in phases.items():
        assert isinstance(deltas, list), f"{label} did not return a list"
        for d in deltas:
            assert isinstance(d, tuple) and len(d) == 3, f"{label}: malformed delta tuple {d!r}"


def test_retraction_emits_negative_diffs_when_supported():
    """Phase 3 must contain at least one `-1` (retraction) entry."""
    run = _import_example()
    phases = run()  # type: ignore[operator]
    p3 = phases["phase3_retraction"]
    assert any(d[2] < 0 for d in p3), f"phase 3 must include at least one negative diff; got {p3!r}"
