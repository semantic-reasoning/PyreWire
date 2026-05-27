"""Regression: `.github/workflows/release.yml` keeps the required steps (#37).

A release pipeline must:
- trigger on `v*` tags;
- verify the tag matches the `pyproject.toml` version;
- publish to PyPI via trusted publishing;
- create a GitHub Release.

If a future refactor accidentally drops any of these, this test fails
loudly. We parse the YAML rather than grep so re-ordering or renaming
keys (where semantically equivalent) is allowed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

yaml = pytest.importorskip("yaml")


def _workflow() -> dict[str, Any]:
    path = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "release.yml"
    assert path.is_file(), f"release workflow missing: {path}"
    return yaml.safe_load(path.read_text())


def test_triggers_on_v_tags():
    wf = _workflow()
    on = wf.get("on") or wf.get(True)  # PyYAML sometimes parses "on:" as True
    assert on is not None, "missing `on:` block"
    push = on.get("push") if isinstance(on, dict) else None
    tags = (push or {}).get("tags") or []
    assert any(t.startswith("v") for t in tags), f"release must trigger on v* tags, got {tags}"


def test_has_publish_job_with_ubuntu():
    wf = _workflow()
    publish = wf["jobs"]["publish"]
    assert "ubuntu" in str(publish.get("runs-on", "")).lower()


def test_publish_job_has_verify_step():
    """A step whose `name` mentions tag/version verification must exist."""
    steps = _workflow()["jobs"]["publish"]["steps"]
    names = [s.get("name", "").lower() for s in steps]
    assert any(
        "verify" in n and "tag" in n for n in names
    ), "release workflow must include a tag-vs-pyproject version check"


def test_publish_step_uses_pypa_action():
    steps = _workflow()["jobs"]["publish"]["steps"]
    uses = [s.get("uses", "") for s in steps]
    assert any(
        "pypa/gh-action-pypi-publish" in u for u in uses
    ), "release workflow must publish through pypa/gh-action-pypi-publish"


def test_download_wheels_uses_node24_artifact_action():
    steps = _workflow()["jobs"]["publish"]["steps"]
    uses = [s.get("uses", "") for s in steps]
    assert "actions/download-artifact@v8.0.1" in uses
    assert "actions/download-artifact@v4" not in uses


def test_creates_github_release():
    steps = _workflow()["jobs"]["publish"]["steps"]
    uses = [s.get("uses", "") for s in steps]
    assert any(
        "softprops/action-gh-release" in u for u in uses
    ), "release workflow must create a GitHub Release"


def test_github_release_uses_extracted_changelog_section():
    steps = _workflow()["jobs"]["publish"]["steps"]
    release_index = next(
        i for i, step in enumerate(steps) if "softprops/action-gh-release" in step.get("uses", "")
    )
    extract_index = next(
        i for i, step in enumerate(steps) if "extract_changelog_section.py" in step.get("run", "")
    )

    assert extract_index < release_index
    extract_step = steps[extract_index]
    assert "${GITHUB_REF_NAME#v}" in extract_step["run"]
    assert "CHANGELOG.md" in extract_step["run"]
    assert "release-notes.md" in extract_step["run"]

    release_with = steps[release_index]["with"]
    assert release_with["body_path"] != "CHANGELOG.md"
    assert "release-notes.md" in release_with["body_path"]
    assert release_with.get("generate_release_notes") is False


def test_id_token_write_for_oidc():
    perms = _workflow().get("permissions", {})
    assert (
        perms.get("id-token") == "write"
    ), "release workflow needs `id-token: write` for PyPI trusted publishing"
