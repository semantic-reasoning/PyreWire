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
    COMPATIBLE_WIRELOG_SERIES,
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


def test_candidate_paths_includes_env_override(monkeypatch, tmp_path):
    """When WIRELOG_LIB is set, it appears first in the candidate list."""
    fake = tmp_path / "libwirelog.so.1"
    monkeypatch.setenv("WIRELOG_LIB", str(fake))
    paths = _candidate_paths()
    assert paths[0] == str(fake)


def test_candidate_paths_includes_wheel_bundled_slot():
    """The wheel-bundled `src/pyrewire/_lib/<soname>` path is always tried."""
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


def test_verify_version_raises_outside_supported_series():
    """Any wirelog outside COMPATIBLE_WIRELOG_SERIES (older minor, newer
    minor, or different major) is rejected with WirelogVersionError."""
    major, minor = COMPATIBLE_WIRELOG_SERIES
    out_of_range = [
        f"{major}.{minor - 1}.0".encode() if minor > 0 else None,
        f"{major}.{minor + 1}.0".encode(),
        f"{major + 1}.0.0".encode(),
    ]
    for reported in filter(None, out_of_range):
        fake = MagicMock()
        fake.wirelog_version_string = lambda r=reported: r
        fake.wirelog_version_string.restype = None
        fake.wirelog_version_string.argtypes = None
        with pytest.raises(WirelogVersionError) as excinfo:
            _verify_version(fake)
        assert reported.decode() in str(excinfo.value)


def test_verify_version_accepts_any_patch_in_series():
    """Every patch release inside COMPATIBLE_WIRELOG_SERIES is accepted —
    pyrewire.__version__ is irrelevant to the comparison."""
    major, minor = COMPATIBLE_WIRELOG_SERIES
    for patch in (0, 1, 99):
        reported = f"{major}.{minor}.{patch}".encode()
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
    # Hide any system-installed libwirelog so ctypes.util.find_library
    # cannot rescue the subprocess. Clear LD_LIBRARY_PATH (Linux),
    # DYLD_LIBRARY_PATH / DYLD_FALLBACK_LIBRARY_PATH (macOS), and
    # PATH so the dynamic linker has no fallback search dirs.
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
