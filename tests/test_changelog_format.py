"""Regression: `CHANGELOG.md` must stay in sync with the project version (#37).

A release is "ready" when the topmost dated section in `CHANGELOG.md`
matches the version in `pyproject.toml`. The `[Unreleased]` section
is allowed (and encouraged) but is ignored for the equality check.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

_toml_loads = tomllib.loads


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


_HEADING_RE = re.compile(r"^##\s+\[([^\]]+)\](?:\s+-\s+\S+)?\s*$", re.MULTILINE)


def _project_version() -> str:
    data = _toml_loads((_repo_root() / "pyproject.toml").read_text())
    return str(data["project"]["version"])


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
    changelog = (_repo_root() / "CHANGELOG.md").read_text()
    top = _topmost_released_version(changelog)
    assert top is not None, "CHANGELOG must have at least one released section"
    assert top == _project_version(), (
        f"CHANGELOG topmost release {top!r} does not match "
        f"pyproject.toml version {_project_version()!r}"
    )


def test_changelog_keep_a_changelog_intro_present():
    text = (_repo_root() / "CHANGELOG.md").read_text()
    assert "Keep a Changelog" in text
