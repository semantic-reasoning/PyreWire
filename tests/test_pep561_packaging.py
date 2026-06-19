# SPDX-License-Identifier: Apache-2.0 OR GPL-3.0-or-later
"""Regression tests for the PEP 561 typing marker shipped in distributions."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import venv
import zipfile
from pathlib import Path

import pytest

_BUILD_AVAILABLE: bool | None = None
_MYPY_AVAILABLE: bool | None = None


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _module_available(module: str) -> bool:
    with tempfile.TemporaryDirectory() as tmpdir:
        return (
            subprocess.run(
                [sys.executable, "-m", module, "--version"],
                check=False,
                capture_output=True,
                cwd=tmpdir,
            ).returncode
            == 0
        )


def _build_available() -> bool:
    global _BUILD_AVAILABLE
    if _BUILD_AVAILABLE is None:
        _BUILD_AVAILABLE = _module_available("build")
    return _BUILD_AVAILABLE


def _mypy_available() -> bool:
    global _MYPY_AVAILABLE
    if _MYPY_AVAILABLE is None:
        _MYPY_AVAILABLE = _module_available("mypy")
    return _MYPY_AVAILABLE


def _venv_python(root: Path) -> Path:
    if sys.platform == "win32":
        return root / "Scripts" / "python.exe"
    return root / "bin" / "python"


def _env_without_repo_pythonpath() -> dict[str, str]:
    repo = _repo_root()
    repo_paths = {str(repo), str(repo / "src")}
    env = os.environ.copy()
    pythonpath = [
        entry
        for entry in env.get("PYTHONPATH", "").split(os.pathsep)
        if entry and entry not in repo_paths
    ]
    if pythonpath:
        env["PYTHONPATH"] = os.pathsep.join(pythonpath)
    else:
        env.pop("PYTHONPATH", None)
    return env


def _build_wheel(out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "build",
            "--wheel",
            "--outdir",
            str(out_dir),
            str(_repo_root()),
        ],
        check=True,
        capture_output=True,
        cwd=str(out_dir),
    )
    wheels = list(out_dir.glob("pyrewire-*.whl"))
    assert len(wheels) == 1, f"expected one wheel, found {wheels}"
    return wheels[0]


@pytest.mark.skipif(not _build_available(), reason="`build` not installed")
def test_wheel_includes_pep561_marker(tmp_path: Path):
    wheel = _build_wheel(tmp_path)

    with zipfile.ZipFile(wheel) as zf:
        names = zf.namelist()

    assert "pyrewire/py.typed" in names


@pytest.mark.skipif(not _build_available(), reason="`build` not installed")
@pytest.mark.skipif(not _mypy_available(), reason="`mypy` not installed")
def test_installed_wheel_is_recognized_as_typed_by_mypy(tmp_path: Path):
    wheel = _build_wheel(tmp_path / "dist")
    venv_dir = tmp_path / "venv"
    venv.EnvBuilder(with_pip=True, system_site_packages=True).create(venv_dir)
    python = _venv_python(venv_dir)

    subprocess.run(
        [str(python), "-m", "pip", "install", "--no-deps", str(wheel)],
        check=True,
        capture_output=True,
        cwd=str(tmp_path),
    )

    program = tmp_path / "downstream.py"
    program.write_text(
        "import pyrewire\n"
        "\n"
        "program: pyrewire.Program | None = None\n"
        "reveal_type(program)\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [str(python), "-m", "mypy", "--no-error-summary", str(program)],
        check=False,
        capture_output=True,
        env=_env_without_repo_pythonpath(),
        text=True,
        cwd=str(tmp_path),
    )

    combined = result.stdout + result.stderr
    assert result.returncode == 0, combined
    assert 'Skipping analyzing "pyrewire"' not in combined
    assert "pyrewire.program.Program | None" in combined
