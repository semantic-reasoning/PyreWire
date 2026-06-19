# SPDX-License-Identifier: Apache-2.0 OR GPL-3.0-or-later
"""Bidirectional `str` ↔ wirelog intern-id cache.

wirelog represents every `STRING` column value as an `int64` id assigned
by an intern table. Forward interning (str → id) is exposed via
`wirelog_easy_intern`; reverse interning (id → str) is **not** exposed
on the public API. PyreWire therefore maintains its own `id → str`
mirror, populated as a side effect of every forward call.

The class takes a callable `intern_fn(bytes) -> int64` so it can be
reused across session kinds. `EasySession` injects
`wirelog_easy_intern`; `Session` (advanced) injects a wrapper that
forwards through `wirelog_program_get_intern` (M2). Callers that learn
about an id by some other channel can use `remember(id, value)` to
seed the cache without touching wirelog.
"""

from __future__ import annotations

import threading
from collections.abc import Callable

from .errors import WirelogInternError


class InternTable:
    """Bidirectional id ↔ string cache, backed by a wirelog intern call."""

    def __init__(self, intern_fn: Callable[[bytes], int]) -> None:
        """`intern_fn(bytes) -> int` must return the id wirelog assigned,
        or a negative number on error."""
        self._intern_fn = intern_fn
        self._forward: dict[str, int] = {}
        self._reverse: dict[int, str] = {}
        self._lock = threading.RLock()

    def intern(self, value: str) -> int:
        """Return the id for `value`, calling wirelog at most once per
        distinct string. Raises `WirelogInternError` if the underlying
        intern call signals failure (return < 0)."""
        with self._lock:
            cached = self._forward.get(value)
            if cached is not None:
                return cached
            rc = int(self._intern_fn(value.encode("utf-8")))
            if rc < 0:
                raise WirelogInternError(f"wirelog intern failed for {value!r} (rc={rc})")
            self._forward[value] = rc
            self._reverse[rc] = value
            return rc

    def lookup(self, sym_id: int) -> str:
        """Reverse intern. Raises `WirelogInternError` if `sym_id` has
        not yet been seen via `intern()` or `remember()`."""
        with self._lock:
            try:
                return self._reverse[int(sym_id)]
            except KeyError as exc:
                raise WirelogInternError(
                    f"intern id {sym_id} has not been seen via forward intern; "
                    "PyreWire cannot reverse-map it. Call intern() with the "
                    "matching string or remember() with the (id, str) pair."
                ) from exc

    def remember(self, sym_id: int, value: str) -> None:
        """Insert an externally-observed (id, value) pair into the cache."""
        with self._lock:
            sid = int(sym_id)
            self._forward[value] = sid
            self._reverse[sid] = value

    def size(self) -> int:
        """Number of distinct (id, value) pairs cached."""
        with self._lock:
            return len(self._forward)

    def contains_id(self, sym_id: int) -> bool:
        with self._lock:
            return int(sym_id) in self._reverse

    def contains_value(self, value: str) -> bool:
        with self._lock:
            return value in self._forward


__all__ = ["InternTable"]
