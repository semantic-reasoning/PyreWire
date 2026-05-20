"""Typed exception hierarchy for wirelog error codes.

Every wirelog C entry point that can fail returns `wirelog_error_t`
(`int`). The `check(rc)` helper converts a non-OK code into the matching
typed Python exception so high-level callers can do
`except CompoundBusyError: retry()` without inspecting integer codes.

Two exception classes have no wirelog counterpart:

- `WirelogVersionError` is raised by the loader on a version mismatch.
- `WirelogModeError` is raised by session classes when `step()` and
  `snapshot()` are mixed inside the same insert batch.
- `WirelogInternError` is raised when a reverse-intern lookup fails.

Implementation note (wirelog 0.40.99): the public ABI does not export
`wirelog_error_string`. Tracked upstream at
semantic-reasoning/wirelog#841. Until the symbol ships, `error_string(rc)`
returns a hard-coded text per `ErrorCode`. When the symbol becomes
available, the helper transparently switches to the wirelog-provided
text without any caller change.
"""
from __future__ import annotations

import ctypes
from typing import Dict, Type

from .._ffi import LIB
from .._ffi._enums import ErrorCode


class WirelogError(Exception):
    """Base class for every wirelog-originated error."""

    code: int = int(ErrorCode.UNKNOWN)


class ParseError(WirelogError):
    """`WIRELOG_ERR_PARSE`. Carries `line`/`column`/`source` when available."""

    code = int(ErrorCode.PARSE)

    def __init__(
        self,
        message: str,
        *,
        line: int | None = None,
        column: int | None = None,
        source: str | None = None,
    ) -> None:
        super().__init__(message)
        self.line = line
        self.column = column
        self.source = source


class InvalidIRError(WirelogError):
    code = int(ErrorCode.INVALID_IR)


class ExecError(WirelogError):
    code = int(ErrorCode.EXEC)


class WirelogMemoryError(WirelogError):
    """`WIRELOG_ERR_MEMORY`. NOT a subclass of built-in `MemoryError`."""

    code = int(ErrorCode.MEMORY)


class WirelogIOError(WirelogError):
    code = int(ErrorCode.IO)


class CompoundSaturatedError(WirelogError):
    code = int(ErrorCode.COMPOUND_SATURATED)


class CompoundBusyError(WirelogError):
    code = int(ErrorCode.COMPOUND_BUSY)


# --- PyreWire-only exception types -----------------------------------------

class WirelogVersionError(WirelogError):
    """libwirelog reports a version different from `pyrewire.__version__`."""


class WirelogModeError(WirelogError):
    """A session call violates the `step()` / `snapshot()` exclusivity rule."""


class WirelogInternError(WirelogError):
    """A symbol id could not be reverse-mapped to its string value."""


# --- Error-code mapping -----------------------------------------------------

_CODE_TO_CLS: Dict[int, Type[WirelogError]] = {
    int(ErrorCode.PARSE): ParseError,
    int(ErrorCode.INVALID_IR): InvalidIRError,
    int(ErrorCode.EXEC): ExecError,
    int(ErrorCode.MEMORY): WirelogMemoryError,
    int(ErrorCode.IO): WirelogIOError,
    int(ErrorCode.COMPOUND_SATURATED): CompoundSaturatedError,
    int(ErrorCode.COMPOUND_BUSY): CompoundBusyError,
}

_FALLBACK_TEXT: Dict[int, str] = {
    int(ErrorCode.OK): "OK",
    int(ErrorCode.PARSE): "parse error",
    int(ErrorCode.INVALID_IR): "invalid IR",
    int(ErrorCode.EXEC): "execution error",
    int(ErrorCode.MEMORY): "out of memory",
    int(ErrorCode.IO): "I/O error",
    int(ErrorCode.COMPOUND_SATURATED): "compound arena saturated",
    int(ErrorCode.COMPOUND_BUSY): "compound arena busy",
    int(ErrorCode.UNKNOWN): "unknown error",
}


def _load_error_string_fn() -> "ctypes._FuncPointer | None":
    """Resolve `wirelog_error_string` once if available; None otherwise.

    Cached on first call. Returns None while wirelog#841 leaves the symbol
    unexported so callers fall back to the local text table.
    """
    try:
        fn = LIB.wirelog_error_string
    except AttributeError:
        return None
    fn.restype = ctypes.c_char_p
    fn.argtypes = [ctypes.c_int]
    return fn


_ERROR_STRING_FN = _load_error_string_fn()


def error_string(rc: int) -> str:
    """Return a human-readable description for `rc`.

    Prefers `LIB.wirelog_error_string(rc)` when available; otherwise
    falls back to a fixed PyreWire-side table. Never raises.
    """
    code = int(rc)
    if _ERROR_STRING_FN is not None:
        try:
            raw = _ERROR_STRING_FN(code)
        except Exception:
            raw = None
        if raw:
            return raw.decode("utf-8", errors="replace")
    return _FALLBACK_TEXT.get(code, f"wirelog_error_t={code}")


def check(rc: int) -> None:
    """Raise the matching `WirelogError` subclass if `rc != WIRELOG_OK`."""
    code = int(rc)
    if code == int(ErrorCode.OK):
        return
    cls = _CODE_TO_CLS.get(code, WirelogError)
    raise cls(error_string(code))


__all__ = [
    "WirelogError",
    "ParseError",
    "InvalidIRError",
    "ExecError",
    "WirelogMemoryError",
    "WirelogIOError",
    "CompoundSaturatedError",
    "CompoundBusyError",
    "WirelogVersionError",
    "WirelogModeError",
    "WirelogInternError",
    "check",
    "error_string",
]
