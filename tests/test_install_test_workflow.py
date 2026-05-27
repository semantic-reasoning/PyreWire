"""Regression: the `install_test` job in wheels.yml stays wired (#33)."""

from __future__ import annotations

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _workflow() -> dict:
    return yaml.safe_load((_repo_root() / ".github" / "workflows" / "wheels.yml").read_text())


def test_install_test_job_exists():
    wf = _workflow()
    assert "install_test" in wf["jobs"], "wheels.yml must define an `install_test` job (#33)"


def test_install_test_depends_on_build_wheels():
    wf = _workflow()
    needs = wf["jobs"]["install_test"].get("needs")
    assert needs == "build_wheels" or "build_wheels" in (
        needs or []
    ), "install_test must `needs: build_wheels` so it runs after the wheels exist"


def test_install_test_matrix_covers_supported_pythons():
    wf = _workflow()
    matrix = wf["jobs"]["install_test"]["strategy"]["matrix"]
    pythons = matrix.get("python") or []
    assert set(pythons) >= {
        "3.11",
        "3.12",
        "3.13",
        "3.14",
    }, f"install_test matrix must cover py3.11-3.14, got {pythons}"
    assert "3.10" not in pythons


def test_install_test_matrix_uses_current_hosted_runners():
    wf = _workflow()
    matrix = wf["jobs"]["install_test"]["strategy"]["matrix"]
    assert matrix["os"] == ["ubuntu-24.04", "macos-15", "windows-2025-vs2026"]


def test_install_test_downloads_built_wheels():
    wf = _workflow()
    steps = wf["jobs"]["install_test"]["steps"]
    uses = [s.get("uses", "") for s in steps]
    assert any(
        "download-artifact" in u for u in uses
    ), "install_test must `download-artifact` the wheels-* artifact"


def test_install_test_sets_opt_in_env():
    wf = _workflow()
    steps = wf["jobs"]["install_test"]["steps"]
    # The step that actually invokes pytest has both `pytest` AND
    # `tests/integration` in its `run` script — the `pip install …
    # pytest` step matches `pytest` alone but isn't what we want.
    run_steps = [
        s
        for s in steps
        if "pytest" in str(s.get("run", "")).lower()
        and "tests/integration" in str(s.get("run", ""))
    ]
    assert run_steps, "install_test must invoke `pytest tests/integration/…`"
    env = run_steps[0].get("env", {})
    assert env.get("PYREWIRE_WHEEL_INSTALL_TEST") == "1", (
        "install_test must set PYREWIRE_WHEEL_INSTALL_TEST=1 so the "
        "wheel-only assertions actually run"
    )


def test_wheel_install_test_file_exists():
    p = _repo_root() / "tests" / "integration" / "test_wheel_install.py"
    assert p.is_file()
