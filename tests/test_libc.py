"""Tests for `pyrewire._core._libc`."""
from __future__ import annotations

import ctypes
import threading

import pytest

from pyrewire._core._libc import libc_free, libc_malloc


def test_malloc_free_roundtrip():
    ptr = libc_malloc(64)
    assert ptr != 0
    libc_free(ptr)


def test_malloc_zero_is_allowed():
    # Per C standard malloc(0) may return either NULL or a unique pointer;
    # both are valid. Just check no exception is raised.
    ptr = libc_malloc(0)
    libc_free(ptr)


def test_malloc_negative_raises():
    with pytest.raises(ValueError):
        libc_malloc(-1)


def test_free_null_is_noop():
    libc_free(0)
    libc_free(None)


def test_free_ctypes_pointer():
    """Accept POINTER-typed values, not just raw ints."""
    ptr = libc_malloc(16)
    typed = ctypes.cast(ptr, ctypes.POINTER(ctypes.c_int64))
    libc_free(typed)


def test_thread_safety_concurrent_first_use():
    """The lazy init must be thread-safe — many threads racing on the
    first `libc_malloc` call should all succeed."""
    results: list[int] = []

    def worker():
        results.append(libc_malloc(8))

    threads = [threading.Thread(target=worker) for _ in range(16)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(results) == 16
    assert all(r != 0 for r in results)
    for r in results:
        libc_free(r)


def test_lazy_init_via_import_does_not_load_libc():
    """Importing this module must not eagerly load libc.

    We exercise this by reading the private cache after fresh import in a
    subprocess to avoid contamination from earlier tests."""
    import subprocess
    import sys
    code = (
        "import sys, os\n"
        "sys.path.insert(0, 'src')\n"
        "import pyrewire._core._libc as m\n"
        "assert m._HANDLE is None, 'libc loaded eagerly'\n"
        "print('OK')\n"
    )
    env = {**__import__('os').environ}
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, env=env, timeout=10,
    )
    assert "OK" in result.stdout, f"stderr={result.stderr!r}"
