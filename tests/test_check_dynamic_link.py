# SPDX-License-Identifier: Apache-2.0 OR GPL-3.0-or-later
"""Tests for `scripts/ci/check_dynamic_link.py` (#32)."""

from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path

import pytest


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _script() -> Path:
    return _repo_root() / "scripts" / "ci" / "check_dynamic_link.py"


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="POSIX-only: NTFS has no executable bit; CI invokes the script via `python <path>`",
)
def test_script_exists_and_is_executable():
    s = _script()
    assert s.is_file()
    assert s.stat().st_mode & 0o111, "check_dynamic_link.py must be executable"


def test_script_rejects_no_args():
    result = subprocess.run(
        [sys.executable, str(_script())],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "usage" in result.stderr.lower()


def test_script_rejects_missing_wheel(tmp_path: Path):
    fake = tmp_path / "nonexistent.whl"
    result = subprocess.run(
        [sys.executable, str(_script()), str(fake)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "missing" in result.stderr.lower() or "no wheels" in result.stderr.lower()


def test_script_rejects_windows_wheel_without_dependency_dlls(tmp_path: Path):
    """A Windows wheel must include wirelog's runtime dependency DLLs."""
    wheel = tmp_path / "pyrewire-1.0.0-cp312-cp312-win_amd64.whl"
    with zipfile.ZipFile(wheel, "w") as zf:
        zf.writestr("pyrewire/__init__.py", "")
        zf.writestr("pyrewire/_lib/__init__.py", "")
        zf.writestr("pyrewire/_lib/wirelog-1.dll", b"stub")
    result = subprocess.run(
        [sys.executable, str(_script()), str(wheel)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "nanoarrow.dll" in result.stderr
    assert "libxxhash.dll" in result.stderr


def test_script_accepts_windows_wheel_with_runtime_dlls(tmp_path: Path):
    """The Windows check is structural and can run on any host OS."""
    wheel = tmp_path / "pyrewire-1.0.0-cp312-cp312-win_amd64.whl"
    with zipfile.ZipFile(wheel, "w") as zf:
        zf.writestr("pyrewire/__init__.py", "")
        zf.writestr("pyrewire/_lib/__init__.py", "")
        zf.writestr("pyrewire/_lib/wirelog-1.dll", b"stub")
        zf.writestr("pyrewire/_lib/nanoarrow.dll", b"stub")
        zf.writestr("pyrewire/_lib/libxxhash.dll", b"stub")
    result = subprocess.run(
        [sys.executable, str(_script()), str(wheel)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"


@pytest.mark.skipif(sys.platform != "linux", reason="linux check path")
def test_script_rejects_wheel_without_libwirelog(tmp_path: Path):
    """A wheel missing the bundled `libwirelog.so*` must fail the gate."""
    wheel = tmp_path / "pyrewire-0.41.0-cp312-cp312-manylinux_2_28_x86_64.whl"
    with zipfile.ZipFile(wheel, "w") as zf:
        zf.writestr("pyrewire/__init__.py", "")
        zf.writestr("pyrewire/_lib/__init__.py", "")
    result = subprocess.run(
        [sys.executable, str(_script()), str(wheel)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "no libwirelog" in result.stderr.lower()


@pytest.mark.skipif(sys.platform != "linux", reason="linux check path")
def test_script_accepts_wheel_with_shared_object(tmp_path: Path):
    """A wheel containing a real `.so` file passes."""
    # Build a tiny shared object from a one-line C source so `file`
    # reports "shared object".
    src = tmp_path / "stub.c"
    src.write_text("int wirelog_stub(void) { return 0; }\n")
    so = tmp_path / "libwirelog.so.1"
    result = subprocess.run(
        ["cc", "-shared", "-fPIC", "-o", str(so), str(src)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.skip("no C compiler available in this env")
    wheel = tmp_path / "pyrewire-0.41.0-cp312-cp312-manylinux_2_28_x86_64.whl"
    with zipfile.ZipFile(wheel, "w") as zf:
        zf.writestr("pyrewire/__init__.py", "")
        zf.write(so, arcname="pyrewire/_lib/libwirelog.so.1")
    result = subprocess.run(
        [sys.executable, str(_script()), str(wheel)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"


def test_wheels_workflow_runs_dynamic_link_check():
    """The dynamic-link script must run in the wheels.yml pipeline."""
    wf = (_repo_root() / ".github" / "workflows" / "wheels.yml").read_text(encoding="utf-8")
    assert "check_dynamic_link.py" in wf
    assert "verify dynamic link" in wf.lower()
