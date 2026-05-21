"""Additional EasySession delta tests (originally from PR #71).

PR #97 shipped `EasySession.step / snapshot / set_delta_callback` on a
clean post-#852 base; this file rebases the unique, functional-only
test coverage from PR #71 onto current `main` without re-introducing
the diagnostic / debugging cruft that motivated those iterations.

The recursive-aggregation cases (mutual reachability) depend on the
wirelog#852 residue fix, so they share the same wirelog-version skip
mark used by `test_easy_step_snapshot.py`.
"""

from __future__ import annotations

from collections import Counter

import pytest

# Mirror the skip guard from test_easy_step_snapshot.py.
try:
    import pyrewire as _pyrewire

    _wirelog_ver = tuple(int(p) for p in _pyrewire.wirelog_version().split("."))
except Exception:
    _wirelog_ver = (0, 0, 0)

pytestmark = pytest.mark.skipif(
    _wirelog_ver <= (0, 41, 0),
    reason=(
        f"step()/deltas need wirelog > 0.41.0 (has wirelog#852); "
        f"running libwirelog reports {'.'.join(str(p) for p in _wirelog_ver)}. "
        "Tracked in wirelog#859."
    ),
)


from pyrewire import EasySession, ExecError, WirelogModeError  # noqa: E402
from pyrewire.session import _Mode  # noqa: E402

_FRIENDSHIP = """
.decl friend(a: symbol, b: symbol)
.decl mutual(a: symbol, b: symbol)
mutual(A, B) :- friend(A, B), friend(B, A).
"""


def _step_until_quiet(session: EasySession, max_iters: int = 16) -> list:
    """Step until two consecutive empty returns or `max_iters` reached.

    wirelog's `step()` advances by one iteration, not to fixpoint;
    a recursive rule may need several iterations before all derived
    rows surface. The first step after a fresh open may also perform
    lazy plan-build and emit no deltas.
    """
    all_deltas: list = []
    empty_streak = 0
    for _ in range(max_iters):
        new = session.step()
        if new:
            all_deltas.extend(new)
            empty_streak = 0
        else:
            empty_streak += 1
            if all_deltas and empty_streak >= 2:
                break
    return all_deltas


def test_schema_for_known_relation_returns_columns():
    with EasySession(_FRIENDSHIP) as s:
        sch = s._schema_for("friend")
        assert sch.relation == "friend"
        assert len(sch.columns) == 2


def test_schema_for_unknown_relation_raises():
    with EasySession(_FRIENDSHIP) as s:
        with pytest.raises(ExecError):
            s._schema_for("nope")


def test_step_produces_mutual_deltas_at_fixpoint():
    with EasySession(_FRIENDSHIP) as s:
        s.insert("friend", ["alice", "bob"])
        s.insert("friend", ["bob", "alice"])
        deltas = _step_until_quiet(s)
        mutual_pos = [d for d in deltas if d[0] == "mutual" and d[2] > 0]
        assert Counter(d[1] for d in mutual_pos) == Counter([("alice", "bob"), ("bob", "alice")])


def test_step_produces_minus_deltas_after_remove():
    with EasySession(_FRIENDSHIP) as s:
        s.insert("friend", ["alice", "bob"])
        s.insert("friend", ["bob", "alice"])
        _step_until_quiet(s)
        s.remove("friend", ["bob", "alice"])
        deltas = _step_until_quiet(s)
        mutual_neg = [d for d in deltas if d[0] == "mutual" and d[2] < 0]
        assert len(mutual_neg) == 2


def test_set_delta_callback_invoked_per_event():
    captured: list = []
    with EasySession(_FRIENDSHIP) as s:
        s.set_delta_callback(lambda d: captured.append(d))
        s.insert("friend", ["alice", "bob"])
        s.insert("friend", ["bob", "alice"])
        all_returned = _step_until_quiet(s)
        assert len(captured) == len(all_returned)
        assert captured == all_returned


def test_set_delta_callback_clear_round_trip():
    """Clear-then-reattach: the reattached callback receives later deltas."""
    seen: list = []
    with EasySession(_FRIENDSHIP) as s:
        s.set_delta_callback(lambda d: None)
        s.set_delta_callback(None)
        s.set_delta_callback(lambda d: seen.append(d))
        s.insert("friend", ["alice", "bob"])
        s.insert("friend", ["bob", "alice"])
        _step_until_quiet(s)
        assert any(d[0] == "mutual" for d in seen)


def test_mode_machine_locks_into_incremental():
    """After step(), `_require_mode(QUERY)` must raise WirelogModeError."""
    with EasySession(_FRIENDSHIP) as s:
        s.step()
        with pytest.raises(WirelogModeError):
            s._require_mode(_Mode.QUERY)


def test_strings_in_step_deltas_are_decoded():
    with EasySession(_FRIENDSHIP) as s:
        s.insert("friend", ["alice", "bob"])
        s.insert("friend", ["bob", "alice"])
        deltas = _step_until_quiet(s)
        for relation, row, _diff in deltas:
            assert isinstance(relation, str)
            if relation == "mutual":
                # No raw int leak for symbol columns of `mutual`.
                for value in row:
                    assert isinstance(value, str)


def test_close_idempotent_after_step():
    s = EasySession(_FRIENDSHIP)
    s.insert("friend", ["alice", "bob"])
    s.insert("friend", ["bob", "alice"])
    _step_until_quiet(s)
    s.close()
    s.close()
