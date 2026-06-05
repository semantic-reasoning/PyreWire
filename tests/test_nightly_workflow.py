"""Regression: `.github/workflows/nightly.yml` keeps required pieces (#52).

The nightly job is the early-warning system for wirelog ABI drift, so
the workflow must:
- run on a schedule (cron),
- build wirelog with `WIRELOG_VERSION: main`,
- run pytest with the coverage gate disabled,
- file/update a `nightly-failure` issue when the tests step fails.

We parse the YAML rather than grep so cosmetic reorders pass cleanly.
"""

from __future__ import annotations

import stat
import sys
from pathlib import Path
from typing import Any

import pytest

yaml = pytest.importorskip("yaml")


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _workflow() -> dict[str, Any]:
    path = _repo_root() / ".github" / "workflows" / "nightly.yml"
    assert path.is_file(), f"missing nightly workflow at {path}"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_nightly_workflow_runs_on_cron():
    wf = _workflow()
    on = wf.get("on") or wf.get(True)  # PyYAML may parse "on:" as True
    assert isinstance(on, dict)
    schedule = on.get("schedule") or []
    assert any(
        isinstance(s, dict) and s.get("cron") for s in schedule
    ), "nightly workflow must declare a `schedule.cron` trigger"


def test_nightly_builds_wirelog_main():
    steps = _workflow()["jobs"]["test_against_main"]["steps"]
    build_steps = [s for s in steps if "wirelog" in str(s.get("name", "")).lower()]
    assert build_steps, "missing wirelog build step"
    env_values = []
    for s in build_steps:
        if isinstance(s.get("env"), dict):
            env_values.extend(s["env"].values())
    assert any(
        str(v).lower() == "main" for v in env_values
    ), "nightly must build wirelog from `main`, not a release tag"


def test_nightly_disables_coverage_gate():
    """The coverage gate is fail-under=90; nightly drops it so wirelog
    breakage surfaces in test failures rather than coverage noise."""
    steps = _workflow()["jobs"]["test_against_main"]["steps"]
    pytest_steps = [s for s in steps if "pytest" in str(s.get("run", "")).lower()]
    assert pytest_steps, "missing pytest step"
    run = pytest_steps[0]["run"]
    assert "addopts=" in run, "nightly pytest must override addopts to drop --cov-fail-under"


def test_nightly_files_failure_issue_on_failure():
    steps = _workflow()["jobs"]["test_against_main"]["steps"]
    failure_steps = [s for s in steps if "nightly-failure" in str(s.get("name", "")).lower()]
    assert failure_steps, "missing nightly-failure file/update step"
    assert "failure" in str(failure_steps[0].get("if", "")).lower()


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="POSIX-only: NTFS has no executable bit; the nightly workflow only runs on ubuntu-24.04",
)
def test_failure_script_exists_and_is_executable():
    script = _repo_root() / "scripts" / "ci" / "open_nightly_failure_issue.sh"
    assert script.is_file()
    # On POSIX the executable bit must be set so the workflow can `bash`
    # it without an explicit `sh` prefix.
    mode = script.stat().st_mode
    assert mode & (
        stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
    ), "open_nightly_failure_issue.sh must be executable"


def test_failure_script_uses_label_and_creates_or_comments():
    script = (_repo_root() / "scripts" / "ci" / "open_nightly_failure_issue.sh").read_text(
        encoding="utf-8"
    )
    assert 'LABEL="nightly-failure"' in script
    assert "gh issue create" in script
    assert "gh issue comment" in script
