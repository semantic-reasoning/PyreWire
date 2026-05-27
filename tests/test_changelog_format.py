"""Regression: `CHANGELOG.md` must stay in sync with the project version (#37).

A release is "ready" when the topmost dated section in `CHANGELOG.md`
matches the version in `pyproject.toml`. The `[Unreleased]` section
is allowed (and encouraged) but is ignored for the equality check.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


_HEADING_RE = re.compile(r"^##\s+\[([^\]]+)\](?:\s+-\s+\S+)?\s*$", re.MULTILINE)
# pyproject.toml is structured; parse only the `version = "..."` field so
# this test stays independent of optional TOML parser availability.
_VERSION_RE = re.compile(r'^version\s*=\s*"([^"]+)"\s*$', re.MULTILINE)


def _project_version() -> str:
    text = (_repo_root() / "pyproject.toml").read_text()
    match = _VERSION_RE.search(text)
    if match is None:
        raise AssertionError('pyproject.toml has no `version = "..."` line')
    return match.group(1)


def _is_nightly_dev_version(version: str) -> bool:
    major, minor, patch, *_ = version.split(".") + ["", "", ""]
    return patch == "99" and major.isdigit() and minor.isdigit()


def _topmost_released_version(changelog_text: str) -> str | None:
    for match in _HEADING_RE.finditer(changelog_text):
        version = match.group(1).strip()
        if version.lower() == "unreleased":
            continue
        return version
    return None


def test_changelog_file_exists():
    assert (_repo_root() / "CHANGELOG.md").is_file()


def test_topmost_released_section_matches_pyproject():
    project_version = _project_version()
    if _is_nightly_dev_version(project_version):
        pytest.skip(
            f"{project_version} tracks wirelog main/nightly and is not a released changelog section"
        )

    changelog = (_repo_root() / "CHANGELOG.md").read_text()
    top = _topmost_released_version(changelog)
    assert top is not None, "CHANGELOG must have at least one released section"
    assert top == project_version, (
        f"CHANGELOG topmost release {top!r} does not match "
        f"pyproject.toml version {project_version!r}"
    )


def test_changelog_keep_a_changelog_intro_present():
    text = (_repo_root() / "CHANGELOG.md").read_text()
    assert "Keep a Changelog" in text
