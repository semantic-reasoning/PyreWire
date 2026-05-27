"""Tests for the libwirelog loader.

This test module is one of the two files allowed (by project convention) to
reach into `pyrewire._ffi` directly: it exercises the loader itself.
"""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import warnings
from unittest.mock import MagicMock

import pytest

# Loader is imported through the public `pyrewire._ffi` re-export so the
# import-time side effects (candidate discovery, library load, version
# verification) all run at module load.
import pyrewire._ffi._loader as loader
from pyrewire._ffi import LIB
from pyrewire._ffi._loader import (
    MINIMUM_WIRELOG_VERSION,
    WirelogVersionError,
    WirelogVersionUnavailableWarning,
    _candidate_paths,
    _parse_version,
    _pep440_base,
    _soname,
    _verify_version,
)


def test_lib_is_loaded_cdll():
    """LIB is a real ctypes.CDLL pointing at the wirelog shared object."""
    assert isinstance(LIB, ctypes.CDLL)
    assert LIB._name  # non-empty path or soname


def test_lib_exposes_sentinel_symbol():
    """The sentinel symbol used to confirm the library is wirelog must resolve."""
    fn = LIB.wirelog_easy_open
    assert fn is not None


def test_candidate_paths_uses_env_override_exclusively(monkeypatch, tmp_path):
    """When WIRELOG_LIB is set, only that explicit path is tried."""
    fake = tmp_path / "libwirelog.so.1"
    monkeypatch.setenv("WIRELOG_LIB", str(fake))
    paths = _candidate_paths()
    assert paths == [str(fake)]


def test_candidate_paths_includes_wheel_bundled_slot(monkeypatch):
    """Without WIRELOG_LIB, the wheel-bundled `<pkg>/_lib/<soname>` path is tried."""
    monkeypatch.delenv("WIRELOG_LIB", raising=False)
    paths = _candidate_paths()
    assert any(p.endswith(os.path.join("_lib", _soname())) for p in paths)


def test_pep440_base_strips_local_version():
    assert _pep440_base("0.40.99") == "0.40.99"
    assert _pep440_base("0.40.99+py1") == "0.40.99"
    assert _pep440_base("0.40.99+py.1.abc") == "0.40.99"


def test_verify_version_warns_when_symbol_unavailable():
    """If the loaded library does not export wirelog_version_string, the
    verifier warns and proceeds — it does not raise. Tracks wirelog#841."""
    fake = MagicMock(spec=[])  # spec=[] -> getattr raises AttributeError
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        _verify_version(fake)
    assert any(
        issubclass(w.category, WirelogVersionUnavailableWarning) for w in caught
    ), f"expected WirelogVersionUnavailableWarning, got {[w.category for w in caught]}"


def test_verify_version_raises_below_minimum():
    """Any wirelog older than MINIMUM_WIRELOG_VERSION is rejected with
    WirelogVersionError."""
    major, minor, patch = MINIMUM_WIRELOG_VERSION
    out_of_range = [
        f"{major}.{minor}.{patch - 1}".encode() if patch > 0 else None,
        f"{major}.{minor - 1}.99".encode() if minor > 0 else None,
        f"{major - 1}.99.99".encode() if major > 0 else None,
    ]
    for reported in filter(None, out_of_range):
        fake = MagicMock()
        fake.wirelog_version_string = lambda r=reported: r
        fake.wirelog_version_string.restype = None
        fake.wirelog_version_string.argtypes = None
        with pytest.raises(WirelogVersionError) as excinfo:
            _verify_version(fake)
        assert reported.decode() in str(excinfo.value)


def test_windows_load_registers_dependency_search_path(monkeypatch, tmp_path):
    """Windows must register the DLL directory before `ctypes.CDLL` loads
    `wirelog-1.dll`, otherwise sibling dependencies may not be found.
    """
    dll = tmp_path / "wirelog-1.dll"
    dll.write_bytes(b"0")

    registered: list[str] = []

    class _Token:
        def __init__(self, path: str) -> None:
            self.path = path

    def fake_add_dll_directory(path: str) -> _Token:
        registered.append(path)
        return _Token(path)

    fake_handle = MagicMock()
    setattr(fake_handle, "wirelog_easy_open", lambda: None)

    def fake_cdll(candidate: str, mode: int | None = None) -> MagicMock:
        return fake_handle

    monkeypatch.setattr(loader.os, "add_dll_directory", fake_add_dll_directory, raising=False)
    monkeypatch.setattr(loader, "ctypes", loader.ctypes)
    monkeypatch.setattr(loader.ctypes, "CDLL", fake_cdll)
    monkeypatch.setattr(loader.sys, "platform", "win32")
    monkeypatch.setattr(loader, "_candidate_paths", lambda: [str(dll)])
    loader._dll_dirs.clear()

    lib = loader.load_libwirelog()
    assert lib is fake_handle
    assert registered == [str(dll.parent)]


def test_verify_version_accepts_minimum_and_newer_versions():
    """The loader accepts the minimum version and newer wirelog builds,
    including future minor releases and main-branch snapshots."""
    major, minor, patch = MINIMUM_WIRELOG_VERSION
    versions = [
        f"{major}.{minor}.{patch}",
        f"{major}.{minor}.{patch + 1}",
        f"{major}.{minor + 1}.0",
        f"{major + 1}.0.0",
    ]
    for version in versions:
        reported = version.encode()
        fake = MagicMock()
        fake.wirelog_version_string = lambda r=reported: r
        fake.wirelog_version_string.restype = None
        fake.wirelog_version_string.argtypes = None
        # Should not raise.
        _verify_version(fake)


def test_parse_version_handles_dotted_strings():
    assert _parse_version("0.41.0") == (0, 41, 0)
    assert _parse_version("0.43.0") == (0, 43, 0)
    assert _parse_version("0.41.99") == (0, 41, 99)
    # Extra dev-tag segments are tolerated.
    assert _parse_version("0.43.0.dev1") == (0, 43, 0)
    # PEP 440 local-version segment is stripped first.
    assert _parse_version("0.41.99+py1") == (0, 41, 99)


def test_missing_library_raises_oserror_listing_candidates(tmp_path):
    """In a clean subprocess where every candidate is invalid, `import
    pyrewire._ffi` fails with an OSError whose message lists each attempt.

    Import-time failure is the intended contract: `pyrewire` cannot be
    used without a discoverable libwirelog, so the failure must surface
    on the first import (not be deferred to first FFI call).
    """
    nonexistent = tmp_path / "definitely-not-here.so"
    code = (
        "import os, sys\n"
        f"os.environ['WIRELOG_LIB'] = {str(nonexistent)!r}\n"
        "sys.path.insert(0, 'src')\n"
        "import pyrewire._ffi\n"
    )
    env = {**os.environ}
    env.pop("WIRELOG_LIB", None)
    # WIRELOG_LIB is an explicit override, so the loader must not fall
    # back to any system-installed libwirelog after this path fails.
    env["LD_LIBRARY_PATH"] = ""
    env["DYLD_LIBRARY_PATH"] = ""
    env["DYLD_FALLBACK_LIBRARY_PATH"] = ""
    env["PATH"] = "/usr/bin:/bin"
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(loader.__file__))))
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=repo_root,
        capture_output=True,
        text=True,
        env=env,
        timeout=15,
    )
    assert result.returncode != 0, f"subprocess unexpectedly succeeded; stderr={result.stderr!r}"
    assert (
        "OSError" in result.stderr or "Could not find libwirelog" in result.stderr
    ), f"OSError not raised at import; stderr={result.stderr!r}"
    assert (
        str(nonexistent) in result.stderr
    ), f"candidate path missing from error message; stderr={result.stderr!r}"
    assert os.path.join("_lib", _soname()) not in result.stderr
