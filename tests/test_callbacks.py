"""Tests for `pyrewire._core.callbacks`."""

from __future__ import annotations

import ctypes
import gc
import weakref

import pytest

from pyrewire._core.callbacks import (
    _REGISTRY,
    CallbackHandle,
    _delta_trampoline,
    _tuple_trampoline,
)


def test_handle_lifecycle_creates_registry_slot():
    cb = CallbackHandle("delta")
    assert cb.token in _REGISTRY
    assert ctypes.cast(cb.user_data, ctypes.c_void_p).value == cb.token
    cb.close()
    assert cb.token not in _REGISTRY


def test_close_is_idempotent():
    cb = CallbackHandle("tuple")
    cb.close()
    cb.close()


def test_rejects_unknown_kind():
    with pytest.raises(ValueError):
        CallbackHandle("nope")


def test_drain_empty_handle_returns_empty_list():
    cb = CallbackHandle("delta")
    try:
        assert cb.drain() == []
    finally:
        cb.close()


def test_delta_trampoline_buffers_events():
    cb = CallbackHandle("delta")
    try:
        row = (ctypes.c_int64 * 2)(1, 2)
        _delta_trampoline(b"r", row, 2, 1, cb.user_data)
        _delta_trampoline(b"r", row, 2, -1, cb.user_data)
        events = cb.drain()
        assert events == [
            ("delta", "r", (1, 2), 1),
            ("delta", "r", (1, 2), -1),
        ]
    finally:
        cb.close()


def test_tuple_trampoline_buffers_events():
    cb = CallbackHandle("tuple")
    try:
        row = (ctypes.c_int64 * 3)(10, 20, 30)
        _tuple_trampoline(b"name", row, 3, cb.user_data)
        events = cb.drain()
        assert events == [("tuple", "name", (10, 20, 30))]
    finally:
        cb.close()


def test_stale_token_invocation_is_safe_noop():
    """If wirelog invokes the trampoline with a token whose registry
    slot has already been cleared, the trampoline must return silently."""
    cb = CallbackHandle("delta")
    stale_token = cb.token
    cb.close()
    assert stale_token not in _REGISTRY
    row = (ctypes.c_int64 * 1)(99)
    _delta_trampoline(b"x", row, 1, 1, ctypes.c_void_p(stale_token))


def test_user_fn_attribute_persists():
    """The user-callable on the state survives drain calls."""
    fn = lambda d: None  # noqa: E731
    cb = CallbackHandle("delta", user_fn=fn)
    try:
        assert cb._state.user_fn is fn
        cb.drain()
        assert cb._state.user_fn is fn
    finally:
        cb.close()


def test_many_handles_get_unique_tokens():
    handles = [CallbackHandle("delta") for _ in range(32)]
    tokens = {h.token for h in handles}
    try:
        assert len(tokens) == 32
    finally:
        for h in handles:
            h.close()


def test_handle_survives_gc_pressure_while_session_holds_ref():
    """As long as a Python caller holds a reference, gc.collect() must
    not yank the registry slot out from under wirelog."""
    cb = CallbackHandle("delta")
    weak = weakref.ref(cb)
    token = cb.token
    try:
        for _ in range(10):
            gc.collect()
        assert weak() is cb
        assert token in _REGISTRY
    finally:
        cb.close()


def test_drain_reraises_callback_error_then_clears_it():
    """If anything inside the trampoline body raises, the exception is
    stashed on the registry slot and `drain()` re-raises it — but the
    trampoline itself returns normally so wirelog never sees a Python
    exception bubble back into the FFI call.

    We exercise the contract by simulating the failure on the state
    object directly (the trampoline's `except BaseException` clause is
    what would store it in production)."""
    cb = CallbackHandle("delta")
    try:
        cb._state.last_error = RuntimeError("simulated callback failure")
        with pytest.raises(RuntimeError, match="simulated callback failure"):
            cb.drain()
        # After drain raises, the error slot is cleared so future drains
        # do not raise the same exception twice.
        assert cb._state.last_error is None
        assert cb.drain() == []
    finally:
        cb.close()


def test_trampoline_call_with_null_user_data_is_safe_noop():
    """Defensive: passing a null `user_data` to the trampoline is a
    no-op rather than a crash. wirelog never produces this, but a
    misuse of the FFI should not segfault."""
    row = (ctypes.c_int64 * 1)(0)
    _delta_trampoline(b"r", row, 1, 1, None)  # must not raise
