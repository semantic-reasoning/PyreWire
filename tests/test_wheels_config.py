"""Regression: cibuildwheel matrix and supporting scripts stay wired (#30 + #31).

The wheel build is what makes `pip install pyrewire` work without a
system wirelog. A future refactor that drops the per-platform
`repair-wheel-command` would silently regress to broken wheels. This
test parses the YAML/TOML and asserts the required pieces exist.
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _read(path: str) -> str:
    return (_repo_root() / path).read_text()


def test_pyproject_has_cibuildwheel_table():
    text = _read("pyproject.toml")
    assert "[tool.cibuildwheel]" in text
    assert "[tool.cibuildwheel.linux]" in text
    assert "[tool.cibuildwheel.macos]" in text
    assert "[tool.cibuildwheel.windows]" in text


def test_pyproject_declares_python_311_plus():
    pyproject = tomllib.loads(_read("pyproject.toml"))
    project = pyproject["project"]
    assert project["requires-python"] == ">=3.11"
    assert "Programming Language :: Python :: 3.10" not in project["classifiers"]
    assert "Programming Language :: Python :: 3.11" in project["classifiers"]
    assert "Programming Language :: Python :: 3.13" in project["classifiers"]
    assert "Programming Language :: Python :: 3.14" in project["classifiers"]


def test_cibuildwheel_drops_cp310():
    pyproject = tomllib.loads(_read("pyproject.toml"))
    build = pyproject["tool"]["cibuildwheel"]["build"]
    assert "cp310" not in build
    assert build == "cp311-* cp312-* cp313-* cp314-*"


def test_wheels_build_matrix_uses_current_hosted_runners():
    wf = yaml.safe_load(_read(".github/workflows/wheels.yml"))
    matrix = wf["jobs"]["build_wheels"]["strategy"]["matrix"]
    assert matrix["os"] == ["ubuntu-24.04", "macos-15", "windows-2025"]


def test_each_platform_has_repair_wheel_command():
    """The wheel-repair step (#31) is what bundles libwirelog into the
    wheel. Missing it on any platform breaks `pip install pyrewire`."""
    text = _read("pyproject.toml")
    sections = re.split(r"\n(?=\[tool\.cibuildwheel\.[a-z]+\])", text)
    for section in sections:
        if section.startswith("[tool.cibuildwheel.linux]"):
            assert "auditwheel repair" in section
        elif section.startswith("[tool.cibuildwheel.macos]"):
            assert "delocate-wheel" in section
        elif section.startswith("[tool.cibuildwheel.windows]"):
            assert "delvewheel repair" in section


def test_wheels_workflow_triggers_on_v_tags_and_dispatch():
    wf = yaml.safe_load(_read(".github/workflows/wheels.yml"))
    on = wf.get("on") or wf.get(True)
    assert isinstance(on, dict)
    push = on.get("push") or {}
    assert "v*" in (push.get("tags") or [])
    assert "workflow_dispatch" in on


def test_wheels_workflow_uploads_artifacts():
    wf = yaml.safe_load(_read(".github/workflows/wheels.yml"))
    steps = wf["jobs"]["build_wheels"]["steps"]
    uses = [s.get("uses", "") for s in steps]
    assert any(
        "upload-artifact" in u for u in uses
    ), "wheels workflow must upload built wheels as artifacts"


def test_wheels_workflow_uses_cibuildwheel_action():
    wf = yaml.safe_load(_read(".github/workflows/wheels.yml"))
    steps = wf["jobs"]["build_wheels"]["steps"]
    assert any("pypa/cibuildwheel" in s.get("uses", "") for s in steps)


def test_cibuildwheel_test_requires_pytest_cov():
    """cibuildwheel runs pytest from a fresh env, so it must install the
    plugin required by pyproject's coverage addopts."""
    pyproject = tomllib.loads(_read("pyproject.toml"))
    requires = pyproject["tool"]["cibuildwheel"]["test-requires"]
    assert "pytest" in requires
    assert "pytest-cov" in requires


def test_wheel_install_workflow_installs_pytest_cov():
    """The wheel install smoke test also runs pytest against this repo's
    pyproject, whose addopts require pytest-cov."""
    wf = yaml.safe_load(_read(".github/workflows/wheels.yml"))
    steps = wf["jobs"]["install_test"]["steps"]
    install_steps = [s for s in steps if "pip install" in str(s.get("run", ""))]
    assert any("pytest-cov" in str(s.get("run", "")) for s in install_steps)


def test_build_wirelog_powershell_script_exists():
    """The Windows runner needs a PowerShell-flavoured build script."""
    ps1 = _repo_root() / "scripts" / "build_wirelog.ps1"
    assert ps1.is_file()
    text = ps1.read_text()
    assert "meson" in text
    assert "WIRELOG_VERSION" in text


@pytest.mark.skipif(
    sys.platform == "win32",
    reason=(
        "POSIX-only: NTFS has no executable bit; "
        "the bash script is consumed by Linux/macOS runners"
    ),
)
def test_build_wirelog_bash_script_exists():
    """The Linux/macOS runners share the bash script."""
    sh = _repo_root() / "scripts" / "build_wirelog.sh"
    assert sh.is_file()
    assert sh.stat().st_mode & 0o111, "build_wirelog.sh must be executable"
