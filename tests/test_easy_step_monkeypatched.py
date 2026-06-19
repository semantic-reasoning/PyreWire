# SPDX-License-Identifier: Apache-2.0 OR GPL-3.0-or-later
"""Monkey-patched tests for `EasySession.step` / `snapshot` /
`set_delta_callback` (#10 + #11).

The functional tests in `test_easy_step_snapshot.py` skip when
libwirelog is older than the wirelog#852 fix. These monkeypatched
tests exercise the same code paths without depending on wirelog
delivering events — they replace `wirelog_easy_step` /
`wirelog_easy_snapshot` / `wirelog_easy_set_delta_cb` with stubs so
the wrappers' control flow is covered regardless of upstream.
"""

from __future__ import annotations

from typing import Any

import pytest

from pyrewire._core.errors import WirelogModeError
from pyrewire._ffi import LIB
from pyrewire.session import EasySession

_SRC = ".decl edge(x: int32, y: int32)\n.decl reach(x: int32)\n"


@pytest.fixture
def session(monkeypatch):
    # Force `wirelog_easy_set_delta_cb` to always succeed without
    # actually wiring up a C callback, since the eager registration
    # in step() / set_delta_callback() would otherwise need a real
    # wirelog session to accept it.
    monkeypatch.setattr(LIB, "wirelog_easy_set_delta_cb", lambda *args: 0)
    monkeypatch.setattr(LIB, "wirelog_easy_step", lambda _h: 0)

    def fake_snapshot(_h: Any, _rel: Any, _cb: Any, _user: Any) -> int:
        return 0

    monkeypatch.setattr(LIB, "wirelog_easy_snapshot", fake_snapshot)
    with EasySession(_SRC) as s:
        yield s


def test_set_delta_callback_registers_a_handle(session):
    """Setting a callback creates the CallbackHandle and the wrapper
    stores the user function on the handle's state slot."""
    fn = lambda _ev: None  # noqa: E731
    session.set_delta_callback(fn)
    assert session._delta_cb is not None
    assert session._delta_cb._state.user_fn is fn


def test_set_delta_callback_none_after_set_clears(session):
    session.set_delta_callback(lambda _ev: None)
    session.set_delta_callback(None)
    assert session._delta_cb is None


def test_set_delta_callback_none_with_no_existing_cb_is_noop(session):
    session.set_delta_callback(None)
    assert session._delta_cb is None


def test_set_delta_callback_rejects_print_delta(session, monkeypatch):
    """The guard from #46 must trigger when the C printer is passed."""
    sentinel = object()

    def fake_is_wirelog(fn: Any) -> bool:
        return fn is sentinel

    monkeypatch.setattr("pyrewire.helpers.is_wirelog_print_delta", fake_is_wirelog)
    with pytest.raises(TypeError, match="abort"):
        session.set_delta_callback(sentinel)  # type: ignore[arg-type]


def test_step_returns_empty_list_when_no_deltas(session):
    """`step()` returns the drained event list — empty when wirelog
    didn't queue anything (stubbed `wirelog_easy_step` does nothing)."""
    assert session.step() == []


def test_step_creates_delta_handle_lazily(session):
    assert session._delta_cb is None
    session.step()
    # step() must have installed the handle for future use.
    assert session._delta_cb is not None


def test_snapshot_returns_empty_list_when_no_tuples(session):
    rows = session.snapshot("reach")
    assert rows == []


def test_snapshot_after_step_raises_mode_error(session):
    session.step()
    with pytest.raises(WirelogModeError):
        session.snapshot("reach")


def test_step_after_snapshot_raises_mode_error(session):
    session.snapshot("reach")
    with pytest.raises(WirelogModeError):
        session.step()


def test_decode_row_decodes_int_columns(session):
    decoded = session._decode_row("edge", (1, 2))
    assert decoded == (1, 2)


def test_decode_row_returns_raw_for_unknown_relation(session):
    decoded = session._decode_row("does_not_exist", (5, 6, 7))
    assert decoded == (5, 6, 7)


def test_decode_row_string_reverse_intern(monkeypatch):
    """For STRING columns, `_decode_row` reverses through `InternTable`."""
    monkeypatch.setattr(LIB, "wirelog_easy_set_delta_cb", lambda *args: 0)
    monkeypatch.setattr(LIB, "wirelog_easy_step", lambda _h: 0)
    with EasySession(".decl name(s: symbol)\n") as s:
        s._intern.remember(42, "alice")
        assert s._decode_row("name", (42,)) == ("alice",)


def test_decode_row_unknown_intern_id_falls_back_to_int(monkeypatch):
    monkeypatch.setattr(LIB, "wirelog_easy_set_delta_cb", lambda *args: 0)
    monkeypatch.setattr(LIB, "wirelog_easy_step", lambda _h: 0)
    with EasySession(".decl name(s: symbol)\n") as s:
        assert s._decode_row("name", (99,)) == (99,)


def test_decode_row_handles_extra_ids():
    """When wirelog returns more ids than the schema declares (e.g.
    auxiliary columns), the trailing ids fall through as raw ints."""
    with EasySession(".decl tiny(x: int32)\n") as s:
        decoded = s._decode_row("tiny", (5, 99, 100))
        assert decoded == (5, 99, 100)


def test_step_with_callback_invokes_user_fn(session):
    """When `step()` has events, the user callback fires per delta.
    We can't make wirelog produce events under monkeypatch, so we
    inject one directly into the trampoline queue and call step()."""
    received: list[Any] = []
    session.set_delta_callback(received.append)
    # Pretend wirelog buffered one delta.
    session._delta_cb._state.queue.append(("delta", "edge", (1, 2), 1))
    decoded = session.step()
    assert decoded == [("edge", (1, 2), 1)]
    assert received == [("edge", (1, 2), 1)]
