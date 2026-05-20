"""Tests for `pyrewire._ffi._advanced` (#20)."""

from __future__ import annotations

import ctypes

import pyrewire._ffi._advanced  # noqa: F401  -- register
import pyrewire._ffi._parser  # noqa: F401  -- for wirelog_parse_string
from pyrewire._ffi import LIB
from pyrewire._ffi._enums import BackendKind
from pyrewire._ffi._types import ProgramHandle, SessionHandle


def test_signatures_attached():
    names = [
        "wirelog_session_create",
        "wirelog_session_destroy",
        "wirelog_session_insert",
        "wirelog_session_remove",
        "wirelog_session_step",
        "wirelog_session_snapshot",
        "wirelog_session_set_delta_cb",
        "wirelog_session_make_compound",
    ]
    for name in names:
        fn = getattr(LIB, name)
        assert fn.argtypes is not None, f"{name} has no argtypes"


def _parse(src: bytes) -> ProgramHandle:
    rc = ctypes.c_int(0)
    h = LIB.wirelog_parse_string(src, ctypes.byref(rc))
    assert h, f"parse rc={rc.value}"
    return ProgramHandle(h)


def test_create_with_default_backend_and_destroy():
    prog = _parse(b".decl x(a: int32)\n")
    sess = SessionHandle()
    try:
        rc = LIB.wirelog_session_create(
            prog,
            ctypes.c_int(int(BackendKind.DEFAULT)),
            ctypes.c_uint32(0),
            ctypes.byref(sess),
        )
        assert rc == 0, f"session_create rc={rc}"
        assert sess.value
        LIB.wirelog_session_destroy(sess)
    finally:
        LIB.wirelog_program_free(prog)


def test_create_with_columnar_backend_and_workers_2():
    prog = _parse(b".decl x(a: int32)\n")
    sess = SessionHandle()
    try:
        rc = LIB.wirelog_session_create(
            prog,
            ctypes.c_int(int(BackendKind.COLUMNAR)),
            ctypes.c_uint32(2),
            ctypes.byref(sess),
        )
        assert rc == 0, f"session_create rc={rc}"
        assert sess.value
        LIB.wirelog_session_destroy(sess)
    finally:
        LIB.wirelog_program_free(prog)


def test_destroy_on_null_handle_is_safe():
    """The header documents `destroy(NULL)` as a no-op; verify ctypes
    rejects nothing and the call completes."""
    null = SessionHandle()  # value=0
    LIB.wirelog_session_destroy(null)  # must not raise
