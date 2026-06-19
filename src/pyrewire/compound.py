# SPDX-License-Identifier: Apache-2.0 OR GPL-3.0-or-later
"""Session-local compound handles (#23).

`wirelog_session_make_compound` and `wirelog_easy_make_compound` return
an opaque `uint64_t` handle that is **only valid until the owning
session is destroyed**. PyreWire wraps that handle in `Compound` and
weakly references the session so:

- Closing the session invalidates every compound it produced.
- Reading `compound.handle` after invalidation raises `ValueError`.
- The Python wrapper does NOT extend the session's lifetime — that
  would defeat the purpose; compounds are cheap views, not co-owners.
"""

from __future__ import annotations

import weakref
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from ._ffi._enums import ColumnType
from ._ffi._types import CompoundArgStruct

if TYPE_CHECKING:  # pragma: no cover
    pass


@dataclass(frozen=True)
class CompoundArg:
    """One argument of a compound. `value` is an `int64` (intern id for
    `STRING` columns)."""

    type: ColumnType
    value: int

    def to_struct(self) -> CompoundArgStruct:
        return CompoundArgStruct(type=int(self.type), value=int(self.value))


class Compound:
    """Session-local compound handle."""

    __slots__ = (
        "_session_ref",
        "functor",
        "arity",
        "_handle",
        "_invalidated",
    )

    def __init__(self, session: Any, functor: str, arity: int, raw_handle: int) -> None:
        if int(raw_handle) == 0:
            raise ValueError(f"compound {functor}/{arity} got a NULL handle from wirelog")
        self._session_ref = weakref.ref(session)
        self.functor: str = functor
        self.arity: int = int(arity)
        self._handle: int = int(raw_handle)
        self._invalidated: bool = False

    @property
    def handle(self) -> int:
        """Return the raw `uint64_t` compound handle.

        Raises `ValueError` if the owning session has been closed (or
        garbage-collected), since wirelog's contract says the handle is
        only valid for the session's lifetime.
        """
        if self._invalidated:
            raise ValueError(
                f"compound {self.functor}/{self.arity} is invalid (explicitly invalidated)"
            )
        sess = self._session_ref()
        if sess is None or getattr(sess, "_closed", False):
            raise ValueError(
                f"compound {self.functor}/{self.arity} is invalid (session has been closed)"
            )
        return self._handle

    def invalidate(self) -> None:
        """Mark this compound as no-longer-usable. Idempotent."""
        self._invalidated = True

    def __repr__(self) -> str:
        state = "invalid" if self._invalidated else f"handle={self._handle:#x}"
        return f"Compound({self.functor}/{self.arity}, {state})"


__all__ = ["Compound", "CompoundArg"]
