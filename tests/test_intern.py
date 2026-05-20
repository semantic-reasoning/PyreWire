"""Tests for `pyrewire._core.intern`."""

from __future__ import annotations

import threading

import pytest

from pyrewire._core.errors import WirelogInternError
from pyrewire._core.intern import InternTable


def make_counter_fn():
    """Return (fn, counter_dict). The fn assigns ids sequentially and
    counts how many times it was actually called."""
    counter = {"calls": 0, "next_id": 1}

    def fn(b: bytes) -> int:
        counter["calls"] += 1
        the_id = counter["next_id"]
        counter["next_id"] += 1
        return the_id

    return fn, counter


def test_intern_caches_repeat_calls():
    fn, counter = make_counter_fn()
    t = InternTable(fn)
    a1 = t.intern("alice")
    a2 = t.intern("alice")
    assert a1 == a2
    assert counter["calls"] == 1


def test_intern_distinct_strings_get_distinct_ids():
    fn, _ = make_counter_fn()
    t = InternTable(fn)
    a = t.intern("alice")
    b = t.intern("bob")
    assert a != b


def test_intern_failure_raises():
    def fn(b: bytes) -> int:
        return -1

    t = InternTable(fn)
    with pytest.raises(WirelogInternError):
        t.intern("nope")


def test_lookup_after_intern():
    fn, _ = make_counter_fn()
    t = InternTable(fn)
    alice_id = t.intern("alice")
    assert t.lookup(alice_id) == "alice"


def test_lookup_unknown_raises_wirelog_intern_error():
    fn, _ = make_counter_fn()
    t = InternTable(fn)
    with pytest.raises(WirelogInternError):
        t.lookup(99)


def test_remember_seeds_both_directions():
    fn, counter = make_counter_fn()
    t = InternTable(fn)
    t.remember(42, "carol")
    # forward lookup must not call fn
    assert t.intern("carol") == 42
    assert counter["calls"] == 0
    # reverse lookup works
    assert t.lookup(42) == "carol"


def test_contains_helpers():
    fn, _ = make_counter_fn()
    t = InternTable(fn)
    t.intern("alice")
    assert t.contains_value("alice")
    assert t.contains_id(1)
    assert not t.contains_value("bob")
    assert not t.contains_id(99)


def test_size_reflects_cache_growth():
    fn, _ = make_counter_fn()
    t = InternTable(fn)
    assert t.size() == 0
    t.intern("a")
    t.intern("b")
    t.intern("a")
    assert t.size() == 2


def test_thread_safety_under_contention():
    """8 threads each intern 1000 distinct strings; final cache has
    8000 unique entries and every id is unique."""
    counter = {"next_id": 1}
    lock = threading.Lock()

    def fn(b: bytes) -> int:
        with lock:
            the_id = counter["next_id"]
            counter["next_id"] += 1
        return the_id

    t = InternTable(fn)

    def worker(prefix: str) -> None:
        for i in range(1000):
            t.intern(f"{prefix}-{i}")

    threads = [threading.Thread(target=worker, args=(f"t{i}",)) for i in range(8)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()

    assert t.size() == 8000
    # Verify reverse map covers every forward entry exactly once.
    ids = set(t._reverse.keys())
    assert len(ids) == 8000
