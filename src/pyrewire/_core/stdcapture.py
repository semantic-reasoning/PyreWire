"""Capture C-level stdout (file descriptor 1) into a Python `BytesIO`.

Several wirelog entry points (`wirelog_optimizer_debug`,
`wirelog_easy_banner`, `wirelog_ir_node_print`) write directly to
stdout from C. The Python `sys.stdout` proxy does not see those writes
because they bypass the Python I/O layer. To make the output usable
from Python we must redirect fd 1 itself: `dup` it aside, replace it
with the write end of a pipe, run the C call, and read from the pipe
in a background draining thread before restoring the original fd.

The draining thread is required because the kernel pipe buffer is
small (typically 64 KiB on Linux). A program that prints more than the
buffer would deadlock on the C-side write call if nothing were
reading concurrently.

Platform support: works on POSIX and on Windows (CPython binds
`os.dup` / `os.dup2` to the CRT). Behaviour around buffered C streams
may differ on Windows; if your callee uses `stdio` rather than the
underlying file descriptor directly, call `fflush(stdout)` from C
before exiting the context (wirelog does this in `optimizer_debug`).
"""

from __future__ import annotations

import contextlib
import ctypes
import os
import sys
import threading
from collections.abc import Iterator
from ctypes.util import find_library
from io import BytesIO
from typing import Any

_FLUSH_RESOLVED = False
_LIBC_FLUSH: Any = None


def _fflush_stdout() -> None:
    """Best-effort flush of C-level `stdout` (NULL flushes all streams).

    Resolved lazily once. Silently no-ops if libc is unreachable, which
    is fine — the capture still works for code that writes via `write(2)`
    directly; it just misses stdio-buffered output from that callee.
    """
    global _LIBC_FLUSH, _FLUSH_RESOLVED
    if not _FLUSH_RESOLVED:
        _FLUSH_RESOLVED = True
        try:
            if sys.platform == "win32":
                lib = ctypes.CDLL("ucrtbase.dll")
            else:
                lib = ctypes.CDLL(find_library("c") or "")
            lib.fflush.argtypes = [ctypes.c_void_p]
            lib.fflush.restype = ctypes.c_int
            _LIBC_FLUSH = lib.fflush
        except OSError:
            _LIBC_FLUSH = None
    if _LIBC_FLUSH is None:
        return
    try:
        _LIBC_FLUSH(None)
    except Exception:
        pass


@contextlib.contextmanager
def capture_c_stdout() -> Iterator[BytesIO]:
    """Redirect fd 1 into a `BytesIO` for the duration of the block.

    Usage:

        with capture_c_stdout() as buf:
            LIB.wirelog_optimizer_debug(prog._handle)
        text = buf.getvalue().decode("utf-8", errors="replace")

    The buffer is appended to live by a background thread; reading
    `.getvalue()` is only safe after the context exits.
    """
    sys.stdout.flush()
    saved_fd = os.dup(1)
    r_fd, w_fd = os.pipe()
    os.dup2(w_fd, 1)
    os.close(w_fd)

    buf = BytesIO()

    def _drain() -> None:
        while True:
            try:
                chunk = os.read(r_fd, 4096)
            except OSError:
                break
            if not chunk:
                break
            buf.write(chunk)

    thread = threading.Thread(target=_drain, daemon=True)
    thread.start()
    try:
        yield buf
    finally:
        sys.stdout.flush()
        # Flush C stdio so any printf-buffered output reaches our pipe
        # before we restore fd 1. (Callees that use `write(2)` directly
        # are unaffected by this.)
        _fflush_stdout()
        os.dup2(saved_fd, 1)
        os.close(saved_fd)
        # Close the read fd to break the drain thread's `read()`.
        try:
            os.close(r_fd)
        except OSError:
            pass
        thread.join(timeout=1.0)


__all__ = ["capture_c_stdout"]
