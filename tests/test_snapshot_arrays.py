"""Tests for `Session.snapshot_arrays` (#28).

`EasySession.snapshot_array` adds the same shape on the easy session
once #10/#11 lands the snapshot method itself (PR #97); the
EasySession-side test will be added at that point.
"""

from __future__ import annotations

from typing import Any

import pytest

np = pytest.importorskip("numpy")


def _wirelog_ver() -> tuple[int, ...]:
    try:
        import pyrewire

        return tuple(int(p) for p in pyrewire.wirelog_version().split("."))
    except Exception:  # noqa: BLE001
        return (0, 0, 0)


pytestmark = pytest.mark.skipif(
    _wirelog_ver() <= (0, 41, 0),
    reason=(
        "snapshot_arrays end-to-end needs wirelog > 0.41.0 (wirelog#852); "
        "tracked in wirelog#859."
    ),
)


from pyrewire._ffi import LIB  # noqa: E402
from pyrewire.program import Program  # noqa: E402
from pyrewire.session import Session  # noqa: E402


def test_snapshot_arrays_returns_dict_of_ndarrays():
    prog = Program.from_string(
        ".decl edge(x: int32, y: int32)\n"
        ".decl reach(x: int32)\n"
        "edge(1, 2). edge(2, 3).\n"
        "reach(X) :- edge(X, _).\n"
    )
    with Session(prog) as s:
        result = s.snapshot_arrays()
    assert isinstance(result, dict)
    for rel, arr in result.items():
        assert isinstance(rel, str)
        assert isinstance(arr, np.ndarray)
        assert arr.dtype == np.int64


def test_snapshot_arrays_raises_without_numpy(monkeypatch):
    """If NumPy is unavailable, `snapshot_arrays` raises RuntimeError."""
    import pyrewire.session as session_mod

    monkeypatch.setattr(session_mod, "_np", None)
    prog = Program.from_string(".decl edge(x: int32, y: int32)\n")
    with Session(prog) as s:
        with pytest.raises(RuntimeError, match="NumPy"):
            s.snapshot_arrays()


def test_snapshot_arrays_groups_by_relation(monkeypatch):
    """Stub `wirelog_session_snapshot` so we can drive the grouping
    code path deterministically without relying on wirelog deltas."""
    prog = Program.from_string(".decl a(x: int32)\n" ".decl b(x: int32, y: int32)\n")

    def fake_snapshot(_h: Any, cb: Any, user: Any) -> int:
        # Push three tuples for relation "a" and two for relation "b".
        from pyrewire._core.callbacks import _REGISTRY

        token = int(getattr(user, "value", 0))
        state = _REGISTRY.get(token)
        if state is None:  # pragma: no cover
            return -1
        state.queue.append(("tuple", "a", (1,)))
        state.queue.append(("tuple", "a", (2,)))
        state.queue.append(("tuple", "a", (3,)))
        state.queue.append(("tuple", "b", (10, 20)))
        state.queue.append(("tuple", "b", (30, 40)))
        return 0

    monkeypatch.setattr(LIB, "wirelog_session_snapshot", fake_snapshot)
    with Session(prog) as s:
        result = s.snapshot_arrays()
    assert set(result) == {"a", "b"}
    assert result["a"].shape == (3, 1)
    assert result["a"].tolist() == [[1], [2], [3]]
    assert result["b"].shape == (2, 2)
    assert result["b"].tolist() == [[10, 20], [30, 40]]
