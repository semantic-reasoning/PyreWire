"""User-facing helpers that mirror or replace unsafe wirelog C utilities.

This module is **process-safe**: every helper degrades gracefully on
inputs that would crash the C equivalent. The most important entry
point is :func:`make_safe_print_delta`, the Python replacement for
`wirelog_easy_print_delta` — the C function calls `abort()` on a
missing reverse-intern, which would terminate the entire Python
process.
"""

from __future__ import annotations

import ctypes
from collections.abc import Callable
from typing import Any

from ._core.errors import WirelogInternError
from ._core.intern import InternTable
from ._ffi import LIB

# Concrete delta event shape passed by the high-level session
# wrappers: (relation_name, decoded_row, diff).
Delta = tuple[str, tuple[Any, ...], int]


def make_safe_print_delta(
    intern: InternTable,
    *,
    file: Any = None,
) -> Callable[[Delta], None]:
    """Return a delta callback that prints rows with reverse-interned
    STRING columns, never aborting on a missing id.

    The C-level ``wirelog_easy_print_delta`` aborts the process when a
    `STRING` column carries an intern id PyreWire's local cache has
    not seen. This Python equivalent falls back to ``<intern:N>`` for
    such ids, keeping the process alive while still surfacing the
    anomaly in the printed output.

    Args:
        intern: the session's `InternTable`. Reverse lookups go through
            its `lookup()`; misses are caught and turned into
            ``<intern:N>``.
        file: an optional writeable text stream. Defaults to
            ``sys.stdout``.

    Returns:
        A callable suitable for
        :meth:`pyrewire.session.EasySession.set_delta_callback` and
        :meth:`pyrewire.session.Session.set_delta_callback`.
    """

    def _print(event: Delta) -> None:
        rel, row, diff = event
        decoded: list[str] = []
        for value in row:
            if isinstance(value, int):
                try:
                    decoded.append(intern.lookup(value))
                except WirelogInternError:
                    decoded.append(f"<intern:{value}>")
            else:
                decoded.append(repr(value))
        sign = "+" if int(diff) > 0 else "-"
        print(f"{sign}{rel}({', '.join(decoded)})", file=file)

    return _print


def is_wirelog_print_delta(fn: Any) -> bool:
    """True if `fn` is the bound ``LIB.wirelog_easy_print_delta`` (or a
    `c_void_p` aliasing the same address).

    The high-level ``set_delta_callback`` methods on the session
    classes use this guard to reject the C printer: it would abort
    the process on missing reverse-interns, which Python callers
    almost never expect.
    """
    target = getattr(LIB, "wirelog_easy_print_delta", None)
    if target is None:
        return False
    if fn is target:
        return True
    try:
        return ctypes.cast(fn, ctypes.c_void_p).value == ctypes.cast(target, ctypes.c_void_p).value
    except (TypeError, ctypes.ArgumentError):
        return False


__all__ = ["Delta", "make_safe_print_delta", "is_wirelog_print_delta"]
