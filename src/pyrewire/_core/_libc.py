"""Lazy, platform-aware libc `malloc`/`free` helper.

Several FFI consumers (parser fact extraction, IR string accessor, IO
adapter read callback) need to allocate or free heap buffers across the
wirelog boundary. Centralising the libc resolution policy here ensures:

- Resolution is lazy. Importing `pyrewire` does NOT load libc; the first
  allocator call does.
- Windows CRT selection is consistent. PyreWire prefers `ucrtbase.dll`
  (the MSVC default since VS 2015 / vcpkg) and falls back to `msvcrt.dll`.
  If a future wirelog build uses a different CRT, free-of-malloc'd buffers
  across the CRT boundary will crash; the assumption is documented here so
  reviewers catch the change.
- All consumers see the same allocator.
"""

from __future__ import annotations

import ctypes
import sys
import threading
from ctypes.util import find_library
from typing import Any

_LOCK = threading.Lock()
_HANDLE: ctypes.CDLL | None = None


def _resolve() -> ctypes.CDLL:
    global _HANDLE
    if _HANDLE is not None:
        return _HANDLE
    with _LOCK:
        if _HANDLE is not None:
            return _HANDLE
        candidate: ctypes.CDLL | None = None
        if sys.platform == "win32":
            for name in ("ucrtbase.dll", "msvcrt.dll"):
                try:
                    candidate = ctypes.CDLL(name, use_errno=True)
                    break
                except OSError:
                    continue
        else:
            libc_name = find_library("c")
            try:
                if libc_name is None:
                    # Last-resort: probe the interpreter's own libc linkage.
                    candidate = ctypes.CDLL(None, use_errno=True)
                else:
                    candidate = ctypes.CDLL(libc_name, use_errno=True)
            except OSError:
                candidate = None
        if candidate is None:
            raise RuntimeError(
                "pyrewire._core._libc: could not load a libc / CRT on this "
                "platform; required for cross-FFI malloc/free."
            )
        candidate.malloc.argtypes = [ctypes.c_size_t]
        candidate.malloc.restype = ctypes.c_void_p
        candidate.free.argtypes = [ctypes.c_void_p]
        candidate.free.restype = None
        _HANDLE = candidate
    return _HANDLE


def libc_malloc(n: int) -> int:
    """Allocate `n` bytes via libc `malloc`. Returns the integer address
    (0 on failure)."""
    if int(n) < 0:
        raise ValueError("libc_malloc: n must be non-negative")
    ptr = _resolve().malloc(ctypes.c_size_t(int(n)))
    return int(ptr) if ptr else 0


def libc_free(ptr: Any) -> None:
    """Free a pointer previously returned by libc `malloc`. NULL is a no-op.

    Accepts either an integer address, `None`, or any ctypes pointer
    (`c_void_p`, `POINTER(T)`).
    """
    if ptr is None:
        return
    if isinstance(ptr, int):
        if ptr == 0:
            return
        _resolve().free(ctypes.c_void_p(ptr))
        return
    # ctypes pointer-like
    _resolve().free(ctypes.cast(ptr, ctypes.c_void_p))


__all__ = ["libc_malloc", "libc_free"]
