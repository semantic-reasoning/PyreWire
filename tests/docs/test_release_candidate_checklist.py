"""Regression coverage for the v1.0.0 release candidate checklist."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

yaml = pytest.importorskip("yaml")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (_repo_root() / path).read_text(encoding="utf-8")


def _mkdocs() -> dict[str, Any]:
    return yaml.safe_load(_read("mkdocs.yml"))


def _checklist() -> str:
    return _read("docs/release-candidate-checklist.md")


def _table_rows() -> list[list[str]]:
    rows: list[list[str]] = []
    for line in _checklist().splitlines():
        if not line.startswith("| "):
            continue
        if set(line.replace("|", "").replace(" ", "").replace("-", "")) == set():
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        rows.append(cells)
    return rows


def test_release_candidate_checklist_is_linked_from_mkdocs_nav():
    assert {"Release candidate checklist": "release-candidate-checklist.md"} in _mkdocs()["nav"]


def test_release_candidate_checklist_table_has_required_columns_and_complete_rows():
    rows = _table_rows()
    assert rows
    assert rows[0] == [
        "Gate",
        "Owner",
        "Verification",
        "Required evidence",
        "Failure action",
    ]

    data_rows = rows[1:]
    assert len(data_rows) >= 10
    for row in data_rows:
        assert len(row) == 5
        gate, owner, verification, evidence, failure_action = row
        assert gate
        assert owner
        assert evidence
        assert "GitHub issue" in failure_action
        assert (
            "Command:" in verification
            or "Workflow:" in verification
            or ("Manual verification" in verification)
        )


def test_release_commit_freeze_and_tag_gating_are_explicit():
    text = _checklist()

    assert "git rev-parse HEAD" in text
    assert "The `v1.0.0` tag must point to that exact SHA" in text
    assert "must not be cut until every gate below passes on the exact release commit" in text
    assert "do not tag or publish" in text


def test_local_source_commands_are_required():
    text = _checklist()
    for command in (
        "black --check .",
        "isort --check-only .",
        "flake8 .",
        "mypy src/pyrewire",
        "pytest -q",
        "mkdocs build --strict",
        "python -m build --sdist",
    ):
        assert command in text


def test_required_workflows_and_release_workflow_guards_are_documented():
    text = _checklist()
    for workflow in (
        ".github/workflows/ci.yml",
        ".github/workflows/docs.yml",
        ".github/workflows/wheels.yml",
        ".github/workflows/release.yml",
    ):
        assert workflow in text

    for release_guard in (
        "builds wheels",
        "runs dynamic-link verification",
        "performs clean install tests",
        "verifies artifacts",
        "publishes only after tag-triggered gates pass",
        "Do not actually tag or publish",
    ):
        assert release_guard in text


def test_wheel_and_clean_install_checks_are_documented():
    text = _checklist()
    for required in (
        "python scripts/ci/check_dynamic_link.py wheelhouse/*.whl",
        "no system `libwirelog`",
        "import `pyrewire`",
        "confirm PyreWire version",
        "confirm bundled wirelog version",
        "integration tests",
    ):
        assert required in text


def test_release_notes_and_consistency_checks_are_documented():
    text = _checklist()
    for required in (
        "v1.0.0 changelog section",
        "GitHub Release body",
        "CHANGELOG.md",
        "package metadata",
        "public API stability",
        "support matrix",
        "security policy",
        "pyproject.toml",
        "SECURITY.md",
    ):
        assert required in text
