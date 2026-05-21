"""Tests for `pyrewire.helpers` (#46)."""

from __future__ import annotations

import io

from pyrewire._core.intern import InternTable
from pyrewire._ffi import LIB
from pyrewire.helpers import is_wirelog_print_delta, make_safe_print_delta


def _intern_table_with(value_id_pairs: dict[str, int]) -> InternTable:
    """Build an InternTable seeded via remember()."""
    fake = InternTable(lambda b: -1)  # forward intern not used
    for value, sym_id in value_id_pairs.items():
        fake.remember(sym_id, value)
    return fake


def test_safe_print_decodes_known_ids():
    intern = _intern_table_with({"alice": 1, "bob": 2})
    buf = io.StringIO()
    fn = make_safe_print_delta(intern, file=buf)
    fn(("friend", (1, 2), 1))
    assert buf.getvalue() == "+friend(alice, bob)\n"


def test_safe_print_unknown_id_falls_back():
    intern = _intern_table_with({})
    buf = io.StringIO()
    fn = make_safe_print_delta(intern, file=buf)
    fn(("friend", (99,), 1))
    # The unmapped id 99 must NOT raise — it prints with the
    # `<intern:N>` marker so user log scrapers can grep for it.
    assert "<intern:99>" in buf.getvalue()


def test_safe_print_handles_remove_diff():
    intern = _intern_table_with({"alice": 1})
    buf = io.StringIO()
    fn = make_safe_print_delta(intern, file=buf)
    fn(("friend", (1,), -1))
    assert buf.getvalue() == "-friend(alice)\n"


def test_safe_print_mixed_typed_columns():
    """Non-int columns (already-decoded strings, floats, bools) print
    via repr — no reverse-intern attempted."""
    intern = _intern_table_with({})
    buf = io.StringIO()
    fn = make_safe_print_delta(intern, file=buf)
    fn(("evt", (1.5, True, "decoded"), 1))
    out = buf.getvalue()
    assert "1.5" in out
    assert "True" in out
    assert "'decoded'" in out


def test_guard_recognises_wirelog_print_delta():
    """`wirelog_easy_print_delta` is the unsafe C entry point we want
    to refuse. The guard must identify it."""
    if not hasattr(LIB, "wirelog_easy_print_delta"):
        # Build doesn't export it — the guard is meaningfully tested
        # only when the symbol is present. Mark as passing.
        return
    assert is_wirelog_print_delta(LIB.wirelog_easy_print_delta)


def test_guard_accepts_normal_callable():
    """Plain Python callables must NOT trigger the guard."""

    def cb(_: object) -> None:
        return None

    assert not is_wirelog_print_delta(cb)
    assert not is_wirelog_print_delta(lambda d: None)
    assert not is_wirelog_print_delta(None)
