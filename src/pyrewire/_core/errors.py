# SPDX-License-Identifier: Apache-2.0 OR GPL-3.0-or-later
"""Typed exception hierarchy for wirelog error codes.

Every wirelog C entry point that can fail returns `wirelog_error_t`
(`int`). The `check(rc)` helper converts a non-OK code into the matching
typed Python exception so high-level callers can do
`except CompoundBusyError: retry()` without inspecting integer codes.

Three exception classes have no wirelog counterpart:

- `WirelogVersionError` is raised when the loaded libwirelog is missing
  an optional capability/symbol required by a PyreWire API (e.g.
  ``Program.relation_ir`` requires ``wirelog_program_get_relation_ir``,
  added in wirelog#860 / > 0.41.0).  It is NOT produced by ``check()``.
- `WirelogModeError` is raised by session classes when an operation is
  attempted in the wrong session mode (step/snapshot/query); the session
  must be closed and reopened to switch modes.  It is NOT produced by
  ``check()``.
- `WirelogInternError` is raised when a reverse-intern lookup fails.

`error_string(rc)` prefers `LIB.wirelog_error_string` (exported since
semantic-reasoning/wirelog#841). If the symbol is missing (pre-#841
builds), it falls back to a PyreWire-side text table indexed by
`ErrorCode`. The fallback is kept indefinitely as a forward-compat
net.
"""

from __future__ import annotations

import ctypes

from .._ffi import LIB
from .._ffi._enums import ErrorCode


class WirelogError(Exception):
    """Base class for every wirelog-originated error."""

    code: int = int(ErrorCode.UNKNOWN)


class ParseError(WirelogError):
    """Raised when the wirelog parser rejects a program (``WIRELOG_ERR_PARSE``, code 1).

    The optional attributes ``line``, ``column``, and ``source`` are
    populated on a best-effort basis.  They are usually ``None`` unless the
    error was raised from file parsing via ``Program.from_file``; string
    parsing via ``Program.from_string`` does not populate them.

    Attributes:
        line: 1-based line number where the parse error occurred, or
            ``None`` if unavailable.
        column: 1-based column number where the parse error occurred, or
            ``None`` if unavailable.
        source: Path to the source file being parsed, or ``None`` if
            unavailable.
    """

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
    """Raised when the program's IR fails structural validation (``WIRELOG_ERR_INVALID_IR``,
    code 2).

    Produced by ``check()`` when the C engine rejects a compiled IR before
    execution begins.  Typically indicates a bug in rule compilation or a
    corrupted program handle.
    """

    code = int(ErrorCode.INVALID_IR)


class ExecError(WirelogError):
    """Catch-all error for runtime failures in the wirelog engine (``WIRELOG_ERR_EXEC``,
    code 3).

    This is the broadest error class in PyreWire.  Beyond engine execution
    failures it is also raised directly (without going through ``check()``)
    for a variety of precondition violations:

    - **Invalid arguments** — e.g. an unknown or undeclared relation name
      (``session.py``, ``program.py``).
    - **Closed or null handles** — operations attempted on a closed
      ``BatchProgram`` or ``Result``, or a NULL handle returned by the C
      library (``batch.py``, ``session.py``).
    - **Missing / unknown relations** — schema lookups that find no entry
      for the requested relation (``program.py``, ``session.py``).
    - **Wirelog call failures** — when the C call returns a non-zero code
      that is not mapped to a more specific subclass.

    When catching engine errors broadly, catch ``ExecError``; for finer
    control catch the more specific subclasses (``ParseError``,
    ``InvalidIRError``, etc.) first.
    """

    code = int(ErrorCode.EXEC)


class WirelogMemoryError(WirelogError):
    """Raised when the wirelog engine cannot allocate memory (``WIRELOG_ERR_MEMORY``,
    code 4).

    This class is intentionally **not** a subclass of the built-in
    ``MemoryError``.  Subclassing ``MemoryError`` can interact badly with
    the CPython interpreter's low-memory handling and recursion-limit
    machinery, producing hard-to-diagnose crashes.  Callers that need to
    catch both should list them explicitly:
    ``except (WirelogMemoryError, MemoryError)``.
    """

    code = int(ErrorCode.MEMORY)


class WirelogIOError(WirelogError):
    """Raised when an I/O adapter registry operation fails (``WIRELOG_ERR_IO``,
    code 5).

    Raised directly (without going through ``check()``) by the I/O adapter
    registry in ``io_adapter.py`` when ``wirelog_io_register_adapter`` or
    ``wirelog_io_unregister_adapter`` returns a non-zero code.  It is also
    reachable via ``check()`` if the C engine returns code 5 for other I/O
    failures.
    """

    code = int(ErrorCode.IO)


class CompoundSaturatedError(WirelogError):
    """Raised when the compound arena's epoch counter is exhausted
    (``WIRELOG_ERR_COMPOUND_SATURATED``, code 6).

    Corresponds to an ``ENOSPC``-style condition: the arena has no more
    epoch slots available and cannot accept new compounds.  This error is
    **not retryable** — the session must be closed and reopened to obtain a
    fresh arena.  See ``docs/semantics/compounds.md`` for the epoch
    lifetime model.
    """

    code = int(ErrorCode.COMPOUND_SATURATED)


class CompoundBusyError(WirelogError):
    """Raised when another worker holds the compound arena epoch
    (``WIRELOG_ERR_COMPOUND_BUSY``, code 7).

    Corresponds to an ``EBUSY``-style condition: the arena epoch is
    currently owned by a concurrent writer.  This error is **transient** —
    callers should retry the operation with an appropriate backoff strategy
    rather than propagating or aborting.
    """

    code = int(ErrorCode.COMPOUND_BUSY)


# --- PyreWire-only exception types -----------------------------------------


class WirelogVersionError(WirelogError):
    """Raised when the loaded libwirelog is missing an optional capability
    required by a PyreWire API.

    This exception has no wirelog C counterpart and is never produced by
    ``check()``.  It acts as a capability/symbol gate: if libwirelog does not
    export a symbol that a PyreWire API requires, that API raises this error
    rather than crashing.  For example, ``Program.relation_ir`` requires
    ``wirelog_program_get_relation_ir`` (added in wirelog#860, > 0.41.0) and
    raises ``WirelogVersionError`` against older libwirelog builds that lack
    it.

    Note: the loader's minimum-version check (``_ffi/_loader.py``) raises a
    plain ``Exception`` subclass (``_loader.WirelogVersionError``), not this
    class.
    """


class WirelogModeError(WirelogError):
    """Raised by session classes when an operation is rejected due to session
    mode exclusivity.

    This exception has no wirelog C counterpart and is never produced by
    ``check()``.  A session commits to a single mode (step, snapshot, or
    query) on its first mode-specific operation.  Any subsequent call that
    requires a different mode raises this error.  To switch modes, close the
    current session and open a new one.
    """


class WirelogInternError(WirelogError):
    """Raised when a symbol id cannot be reverse-mapped to its string value.

    This exception has no wirelog C counterpart and is never produced by
    ``check()``.  It is raised by the intern table when a numeric symbol id
    is looked up but has no corresponding string entry, indicating an
    internal consistency error.
    """


# --- Error-code mapping -----------------------------------------------------

_CODE_TO_CLS: dict[int, type[WirelogError]] = {
    int(ErrorCode.PARSE): ParseError,
    int(ErrorCode.INVALID_IR): InvalidIRError,
    int(ErrorCode.EXEC): ExecError,
    int(ErrorCode.MEMORY): WirelogMemoryError,
    int(ErrorCode.IO): WirelogIOError,
    int(ErrorCode.COMPOUND_SATURATED): CompoundSaturatedError,
    int(ErrorCode.COMPOUND_BUSY): CompoundBusyError,
}

_FALLBACK_TEXT: dict[int, str] = {
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


def _load_error_string_fn() -> ctypes._FuncPointer | None:
    """Resolve `wirelog_error_string` once if available; None otherwise.

    Returns None against pre-#841 builds so callers fall back to the
    local text table.
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
            return raw.decode("utf-8", errors="replace")  # type: ignore[no-any-return]
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
