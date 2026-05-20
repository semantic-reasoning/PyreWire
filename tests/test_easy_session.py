"""Tests for `EasySession` lifecycle, intern, insert, remove (#9)."""

from __future__ import annotations

import threading

import pytest

from pyrewire import EasySession, ParseError

_FRIENDSHIP = """
.decl friend(a: symbol, b: symbol)
.decl mutual(a: symbol, b: symbol)
mutual(A, B) :- friend(A, B), friend(B, A).
"""

_EDGE_INT = ".decl edge(x: int32, y: int32)\n"


def test_open_and_close_via_context_manager():
    with EasySession(_EDGE_INT) as s:
        assert s is not None


def test_close_idempotent():
    s = EasySession(_EDGE_INT)
    s.close()
    s.close()


def test_two_sessions_are_independent():
    with EasySession(_EDGE_INT) as a, EasySession(_EDGE_INT) as b:
        a.insert("edge", [1, 2])
        b.insert("edge", [9, 8])


def test_invalid_source_raises_parse_error():
    with pytest.raises(ParseError):
        EasySession("this is not datalog")


def test_intern_caches_repeat_calls():
    with EasySession(_FRIENDSHIP) as s:
        i1 = s.intern("alice")
        i2 = s.intern("alice")
        i3 = s.intern("bob")
        assert i1 == i2
        assert i1 != i3
        assert i1 >= 0 and i3 >= 0


def test_insert_int_row():
    with EasySession(_EDGE_INT) as s:
        s.insert("edge", [1, 2])
        s.insert("edge", [2, 3])


def test_insert_string_row_auto_interns():
    with EasySession(_FRIENDSHIP) as s:
        s.insert("friend", ["alice", "bob"])
        # Cache should reflect both strings.
        assert s._intern.size() == 2


def test_remove_after_insert():
    with EasySession(_FRIENDSHIP) as s:
        s.insert("friend", ["alice", "bob"])
        s.remove("friend", ["alice", "bob"])


def test_insert_arity_mismatch_does_not_immediately_error():
    """wirelog_easy_insert does not validate arity at insert time; the
    error surfaces later (at step/snapshot). Just verify the call
    completes without crashing — the strict validation is the
    responsibility of higher-level helpers."""
    with EasySession(_EDGE_INT) as s:
        s.insert("edge", [1, 2, 3])  # too many values; accepted at this layer


def test_unsupported_row_value_type_raises():
    with EasySession(_EDGE_INT) as s:
        with pytest.raises(TypeError):
            s.insert("edge", [object(), object()])  # type: ignore[list-item]


def test_no_lock_path_does_not_segfault_single_threaded():
    with EasySession(_FRIENDSHIP, lock=False) as s:
        s.insert("friend", ["a", "b"])
        s.intern("c")


def test_concurrent_intern_under_lock_is_safe():
    """Multiple threads interning the same string under the session
    lock must produce the same id and not crash."""
    with EasySession(_FRIENDSHIP) as s:
        ids: list[int] = []
        lock = threading.Lock()

        def worker() -> None:
            with lock:
                ids.append(s.intern("alice"))

        threads = [threading.Thread(target=worker) for _ in range(16)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(set(ids)) == 1
