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


def _section(changelog_text: str, heading: str) -> str:
    match = re.search(rf"^##\s+\[{re.escape(heading)}\].*$", changelog_text, re.MULTILINE)
    assert match is not None, f"CHANGELOG missing [{heading}] section"
    section_start = match.start()
    search_start = match.end()
    next_heading = re.search(r"^##\s+", changelog_text[search_start:], re.MULTILINE)
    end = len(changelog_text)
    if next_heading is not None:
        end = search_start + next_heading.start()
    return changelog_text[slice(section_start, end)].strip()


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


def test_unreleased_section_is_empty_for_100_release():
    changelog = (_repo_root() / "CHANGELOG.md").read_text()
    assert _section(changelog, "Unreleased") == "## [Unreleased]"


def test_100_release_notes_include_publishable_contract_facts():
    changelog = (_repo_root() / "CHANGELOG.md").read_text()
    section = _section(changelog, "1.0.0")
    rendered_text = re.sub(r"\s+", " ", section)

    for expected in (
        "first stable release",
        "supported public API boundary",
        "v1.0.x as the security-supported release line",
        "Stable top-level exports now include",
        "incremental session classes: `EasySession` and `Session`",
        "batch execution classes: `BatchProgram` and `Result`",
        "Backward-incompatible changes require a new major version",
        "deprecated public APIs will remain available for at least one minor release",
        "CPython 3.11, 3.12, 3.13, and 3.14",
        "Linux `manylinux_2_28` `x86_64`",
        "macOS `arm64` only",
        "Windows `AMD64`",
        "Wheels bundle `libwirelog`",
        "Source distributions do not bundle `libwirelog`",
        "`WIRELOG_LIB`",
        "wirelog v0.44.0",
        "5bebc8d40bbb850179fbb091807964762df5a814",
        "minimum compatible runtime wirelog version is 0.44.0",
        "GitHub release automation extracts this exact tagged changelog section",
        "`EasySession`",
        "`Session`",
        "`BatchProgram`",
        "`Result`",
        "`Program`",
        "`Schema`",
        "`IRNode`",
        "`AsyncEasySession`",
        "`AsyncSession`",
        "`AsyncBatchProgram`",
        "`IOContext`",
        "`register_adapter`",
        "`unregister_adapter`",
        "`registered_schemes`",
        "`Compound`",
        "`ErrorCode`",
        "`WirelogError`",
        "`wirelog_version`",
        "`build_config`",
        "`Delta`",
    ):
        assert expected in rendered_text

    assert "AsyncSession` provides the async incremental session surface" in rendered_text

    for non_top_level in ("`Adapter`", "`check`", "`error_string`"):
        assert non_top_level not in section

    assert not re.search(r"AsyncEasySession[^.\n]*(?:step|snapshot)", section)
    assert "step and snapshot mirrors" not in section

    for stale in ("future-work", "forthcoming", "0.41.99", "universal2", "macOS Intel"):
        assert stale not in section


def test_100_release_compare_links_are_tag_to_tag():
    changelog = (_repo_root() / "CHANGELOG.md").read_text()

    assert (
        "[Unreleased]: https://github.com/semantic-reasoning/PyreWire/compare/v1.0.0...HEAD"
        in changelog
    )
    assert (
        "[1.0.0]: https://github.com/semantic-reasoning/PyreWire/compare/v0.41.0...v1.0.0"
        in changelog
    )
