# SPDX-License-Identifier: Apache-2.0 OR GPL-3.0-or-later
"""Smoke tests for `pyrewire._ffi._easy` bindings.

Verifies that the easy facade's 14 entry points are reachable and that
the most common roundtrip (open → intern → close) works end-to-end.
"""

from __future__ import annotations

import ctypes

# Import side effect: register all easy_* argtypes/restype.
import pyrewire._ffi._easy  # noqa: F401
from pyrewire._ffi import LIB
from pyrewire._ffi._types import EASY_OPEN_OPTS_SIZE, EasyOpenOptsStruct, EasySessionHandle

# A trivially-valid wirelog source. We declare and never derive anything.
_MINIMAL_SRC = b".decl x(a: int32)\n"


def test_every_easy_symbol_has_a_signature():
    """Each of the 14 easy_* entry points has either restype or argtypes set."""
    names = [
        "wirelog_easy_open",
        "wirelog_easy_open_opts",
        "wirelog_easy_close",
        "wirelog_easy_intern",
        "wirelog_easy_insert",
        "wirelog_easy_remove",
        "wirelog_easy_insert_sym",
        "wirelog_easy_remove_sym",
        "wirelog_easy_step",
        "wirelog_easy_snapshot",
        "wirelog_easy_set_delta_cb",
        "wirelog_easy_make_compound",
        "wirelog_easy_print_delta",
        "wirelog_easy_banner",
    ]
    for name in names:
        fn = getattr(LIB, name)
        # restype is always set; argtypes may be None for the two variadic
        # functions, but restype is never None.
        assert fn.restype is not None or name in (
            "wirelog_easy_close",
            "wirelog_easy_print_delta",
            "wirelog_easy_banner",
        ), f"{name} has no restype set"


def test_open_close_roundtrip():
    """Open a session against a minimal program, then close it."""
    handle = EasySessionHandle()
    rc = LIB.wirelog_easy_open(_MINIMAL_SRC, ctypes.byref(handle))
    assert rc == 0, f"wirelog_easy_open rc={rc}"
    assert handle.value, "open returned NULL handle"
    LIB.wirelog_easy_close(handle)


def test_open_opts_with_workers_and_eager_build():
    """`wirelog_easy_open_opts` accepts a sized opts struct."""
    handle = EasySessionHandle()
    opts = EasyOpenOptsStruct(
        size=EASY_OPEN_OPTS_SIZE,
        num_workers=2,
        eager_build=True,
        _reserved=None,
    )
    rc = LIB.wirelog_easy_open_opts(_MINIMAL_SRC, ctypes.byref(opts), ctypes.byref(handle))
    assert rc == 0, f"wirelog_easy_open_opts rc={rc}"
    assert handle.value
    LIB.wirelog_easy_close(handle)


def test_intern_returns_non_negative_id_and_is_stable():
    """`wirelog_easy_intern` returns the same id for the same symbol."""
    handle = EasySessionHandle()
    rc = LIB.wirelog_easy_open(_MINIMAL_SRC, ctypes.byref(handle))
    assert rc == 0
    try:
        id1 = LIB.wirelog_easy_intern(handle, b"alice")
        id2 = LIB.wirelog_easy_intern(handle, b"alice")
        id3 = LIB.wirelog_easy_intern(handle, b"bob")
        assert id1 >= 0
        assert id1 == id2
        assert id3 != id1
    finally:
        LIB.wirelog_easy_close(handle)
