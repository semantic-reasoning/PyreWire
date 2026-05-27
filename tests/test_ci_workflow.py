"""Regression coverage for the main CI workflow."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

yaml = pytest.importorskip("yaml")


def _workflow_text() -> str:
    path = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "ci.yml"
    assert path.is_file(), f"CI workflow missing: {path}"
    return path.read_text()


def _workflow() -> dict[str, Any]:
    return yaml.safe_load(_workflow_text())


def test_ci_default_wirelog_version_is_exact_sha():
    env = _workflow()["jobs"]["test"]["env"]
    default = str(env["WIRELOG_VERSION"])
    assert "5bebc8d40bbb850179fbb091807964762df5a814" in default


def test_ci_matrix_drops_python_310():
    matrix = _workflow()["jobs"]["test"]["strategy"]["matrix"]
    pythons = matrix["python"]
    assert pythons == ["3.11", "3.12", "3.13"]


def test_ci_workflow_has_least_privilege_permissions():
    assert _workflow()["permissions"] == {"contents": "read"}


def test_ci_wirelog_sha_resolver_accepts_exact_sha():
    text = _workflow_text()
    assert "^[0-9a-fA-F]{40}$" in text
    assert 'sha="$WIRELOG_VERSION"' in text
    assert "git ls-remote" in text
