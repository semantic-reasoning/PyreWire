"""Tests for `pyrewire._core.errors`."""
from __future__ import annotations

import pytest

from pyrewire._core.errors import (
    CompoundBusyError,
    CompoundSaturatedError,
    ExecError,
    InvalidIRError,
    ParseError,
    WirelogError,
    WirelogIOError,
    WirelogInternError,
    WirelogMemoryError,
    WirelogModeError,
    WirelogVersionError,
    _FALLBACK_TEXT,
    check,
    error_string,
)
from pyrewire._ffi._enums import ErrorCode


def test_check_ok_is_noop():
    assert check(0) is None
    assert check(int(ErrorCode.OK)) is None


@pytest.mark.parametrize(
    "code, cls",
    [
        (ErrorCode.PARSE, ParseError),
        (ErrorCode.INVALID_IR, InvalidIRError),
        (ErrorCode.EXEC, ExecError),
        (ErrorCode.MEMORY, WirelogMemoryError),
        (ErrorCode.IO, WirelogIOError),
        (ErrorCode.COMPOUND_SATURATED, CompoundSaturatedError),
        (ErrorCode.COMPOUND_BUSY, CompoundBusyError),
    ],
)
def test_check_raises_matching_subclass(code, cls):
    with pytest.raises(cls) as exc:
        check(int(code))
    assert exc.value.code == int(code)
    assert isinstance(exc.value, WirelogError)


def test_check_unknown_code_falls_back_to_base():
    with pytest.raises(WirelogError) as exc:
        check(99)
    # 99 is not in _CODE_TO_CLS but also not OK, so the base class fires.
    assert type(exc.value) is WirelogError


def test_error_string_returns_str_for_each_known_code():
    for code in _FALLBACK_TEXT:
        s = error_string(code)
        assert isinstance(s, str)
        assert s  # non-empty


def test_error_string_unknown_code_yields_synthetic_text():
    s = error_string(7777)
    assert "7777" in s


def test_parse_error_carries_optional_fields():
    e = ParseError("bad token", line=3, column=12, source="x.dl")
    assert str(e) == "bad token"
    assert e.line == 3
    assert e.column == 12
    assert e.source == "x.dl"
    assert e.code == int(ErrorCode.PARSE)


def test_parse_error_defaults_are_none():
    e = ParseError("oops")
    assert e.line is None
    assert e.column is None
    assert e.source is None


def test_pyrewire_only_exceptions_inherit_from_wirelog_error():
    for cls in (WirelogVersionError, WirelogModeError, WirelogInternError):
        assert issubclass(cls, WirelogError)


def test_wirelog_memory_error_is_not_builtin_memory_error():
    """Subclassing built-in MemoryError causes interpreter surprises around
    recursion limits; the PyreWire variant is intentionally distinct."""
    assert not issubclass(WirelogMemoryError, MemoryError)


def test_check_uses_error_string_text():
    """The exception message must include the human-readable error text,
    whether it comes from libwirelog or the fallback table."""
    try:
        check(int(ErrorCode.PARSE))
    except ParseError as exc:
        assert str(exc) == error_string(int(ErrorCode.PARSE))
