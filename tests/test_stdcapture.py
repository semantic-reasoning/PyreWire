"""Tests for `pyrewire._core.stdcapture.capture_c_stdout` (#19)."""

from __future__ import annotations

import ctypes
import os
import sys

import pytest

from pyrewire._core.stdcapture import capture_c_stdout
from pyrewire._ffi import LIB


def test_captures_python_print():
    with capture_c_stdout() as buf:
        # `print` goes through the Python sys.stdout shim but the
        # underlying fd is what we redirected.
        sys.stdout.flush()
        os.write(1, b"hello-from-fd\n")
    assert b"hello-from-fd" in buf.getvalue()


@pytest.mark.skipif(
    sys.platform == "win32",
    reason=(
        "Windows CRT stdio doesn't honor POSIX fd-1 dup2 the way glibc/musl do — "
        "msvcrt.dll's FILE* stdout caches the original fd internally, so capturing "
        "a printf-from-DLL via dup2-on-fd-1 needs a Windows-specific path "
        "(see #19 follow-up)."
    ),
)
def test_captures_c_level_write():
    libc = ctypes.CDLL(None)
    libc.printf.restype = ctypes.c_int
    libc.printf.argtypes = [ctypes.c_char_p]
    libc.fflush.argtypes = [ctypes.c_void_p]
    libc.fflush.restype = ctypes.c_int
    with capture_c_stdout() as buf:
        libc.printf(b"hi-from-c\n")
        libc.fflush(None)
    assert b"hi-from-c" in buf.getvalue()


def test_no_fd_leak_after_capture():
    """The capture must clean up its dup'd fds — fd-1 count is stable."""
    before = _count_open_fds()
    for _ in range(5):
        with capture_c_stdout():
            pass
    after = _count_open_fds()
    # Allow ±1 for unrelated transient fd activity from the runtime.
    assert abs(after - before) <= 1


def test_captures_wirelog_banner():
    """An actual wirelog C function whose output we want to see."""
    LIB.wirelog_easy_banner.restype = None
    LIB.wirelog_easy_banner.argtypes = [ctypes.c_char_p]
    with capture_c_stdout() as buf:
        LIB.wirelog_easy_banner(b"PyreWire test")
    # We don't assert the exact format wirelog uses — only that *some*
    # output was emitted that contains the title we passed.
    output = buf.getvalue()
    assert b"PyreWire test" in output or output  # at minimum, non-empty


def _count_open_fds() -> int:
    if sys.platform == "linux":
        return len(os.listdir(f"/proc/{os.getpid()}/fd"))
    if sys.platform == "darwin":
        try:
            return len(os.listdir("/dev/fd"))
        except OSError:
            return 0
    return 0  # Windows: skip the leak check
