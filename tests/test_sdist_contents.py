"""Regression: PyreWire sdist must never ship a wirelog binary.

The dual-license boundary requires that the wirelog shared library is
never inside an sdist tarball — it is bundled into wheels at build
time by `auditwheel` / `delocate` / `delvewheel`, but the sdist's
`src/pyrewire/_lib/` directory stays empty (apart from `__init__.py`).
A developer who has built `libwirelog.so.1` into the `_lib` directory
locally must NOT produce a tarball that smuggles it through.
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

_BUILD_AVAILABLE: bool | None = None


def _build_available() -> bool:
    global _BUILD_AVAILABLE
    if _BUILD_AVAILABLE is not None:
        return _BUILD_AVAILABLE
    _BUILD_AVAILABLE = importlib.util.find_spec("build.__main__") is not None
    return _BUILD_AVAILABLE


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


FORBIDDEN = re.compile(r"_lib/.*\.(so|dylib|dll|pyd)(\.\d.*)?$")


def _build_sdist(out_dir: Path) -> Path:
    """Build an sdist of the repo into `out_dir`; return the archive path."""
    subprocess.run(
        [
            sys.executable,
            "-m",
            "build",
            "--sdist",
            "--outdir",
            str(out_dir),
            str(_repo_root()),
        ],
        check=True,
        capture_output=True,
        cwd=str(out_dir),
    )
    archives = list(out_dir.glob("pyrewire-*.tar.gz"))
    assert len(archives) == 1, f"expected one sdist, found {archives}"
    return archives[0]


@pytest.mark.skipif(not _build_available(), reason="`build` not installed")
def test_sdist_excludes_wirelog_binaries(tmp_path: Path):
    """Plant a fake `libwirelog.so.1` in `_lib/` and confirm it does
    not survive the sdist build."""
    fake = _repo_root() / "src" / "pyrewire" / "_lib" / "libwirelog.so.1"
    fake.write_bytes(b"NOT A REAL BINARY")
    try:
        archive = _build_sdist(tmp_path)
        bad = []
        with tarfile.open(archive, "r:gz") as tf:
            for name in tf.getnames():
                if FORBIDDEN.search(name):
                    bad.append(name)
        assert not bad, "sdist contains wirelog binaries: " + ", ".join(bad)
    finally:
        try:
            fake.unlink()
        except OSError:
            pass


@pytest.mark.skipif(not _build_available(), reason="`build` not installed")
def test_sdist_keeps_lib_init_placeholder(tmp_path: Path):
    """The empty `_lib/__init__.py` placeholder MUST stay in the sdist
    so wheel-repair has a directory to populate later."""
    archive = _build_sdist(tmp_path)
    with tarfile.open(archive, "r:gz") as tf:
        names = tf.getnames()
    assert any(
        n.endswith("src/pyrewire/_lib/__init__.py") for n in names
    ), "sdist must keep the _lib/__init__.py placeholder"
