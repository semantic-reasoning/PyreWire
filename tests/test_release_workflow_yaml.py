"""Regression: `.github/workflows/release.yml` keeps the required steps (#37).

A release pipeline must:
- trigger on `v*` tags;
- verify the tag matches the `pyproject.toml` version;
- build and install-test wheels in the release workflow;
- publish only after release-local wheels and sdist are verified;
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


def test_release_workflow_has_build_install_publish_dag():
    jobs = _workflow()["jobs"]
    assert {"build_wheels", "install_test", "build_sdist", "publish"} <= set(jobs)

    assert jobs["install_test"].get("needs") == "build_wheels" or "build_wheels" in (
        jobs["install_test"].get("needs") or []
    )
    publish_needs = jobs["publish"].get("needs") or []
    assert "install_test" in publish_needs
    assert "build_sdist" in publish_needs


def test_release_workflow_has_verify_step():
    """A step whose `name` mentions tag/version verification must exist."""
    jobs = _workflow()["jobs"].values()
    names = [s.get("name", "").lower() for job in jobs for s in job.get("steps", [])]
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


def test_release_has_no_disabled_or_sdist_only_wheel_download():
    text = (
        Path(__file__).resolve().parent.parent / ".github" / "workflows" / "release.yml"
    ).read_text()
    assert "if: ${{ false }}" not in text
    assert "sdist only" not in text.lower()


def test_release_build_wheels_matrix_matches_supported_runners():
    matrix = _workflow()["jobs"]["build_wheels"]["strategy"]["matrix"]
    assert matrix["os"] == ["ubuntu-24.04", "macos-15", "windows-2025-vs2026"]


def test_release_build_wheels_runs_dynamic_link_check_before_upload():
    steps = _workflow()["jobs"]["build_wheels"]["steps"]
    dynamic_idx = next(
        i for i, step in enumerate(steps) if "check_dynamic_link.py" in step.get("run", "")
    )
    upload_idx = next(
        i for i, step in enumerate(steps) if step.get("uses") == "actions/upload-artifact@v7.0.1"
    )
    upload_with = steps[upload_idx]["with"]

    assert dynamic_idx < upload_idx
    assert upload_with["name"] == "wheels-${{ matrix.os }}"
    assert upload_with["path"] == "./wheelhouse/*.whl"
    assert upload_with["if-no-files-found"] == "error"


def test_release_install_test_gates_publish_and_uses_supported_matrix():
    jobs = _workflow()["jobs"]
    install_test = jobs["install_test"]
    matrix = install_test["strategy"]["matrix"]

    assert jobs["publish"]["needs"] == ["install_test", "build_sdist"]
    assert install_test["needs"] == "build_wheels"
    assert matrix["os"] == ["ubuntu-24.04", "macos-15", "windows-2025-vs2026"]
    assert matrix["python"] == ["3.11", "3.12", "3.13", "3.14"]


def test_release_install_test_downloads_matching_wheels_and_runs_integration_tests():
    steps = _workflow()["jobs"]["install_test"]["steps"]
    download_steps = [s for s in steps if s.get("uses") == "actions/download-artifact@v8.0.1"]
    assert download_steps
    assert download_steps[0]["with"]["name"] == "wheels-${{ matrix.os }}"
    assert download_steps[0]["with"]["path"] == "dist"

    combined_runs = "\n".join(str(s.get("run", "")) for s in steps)
    assert "dist/pyrewire-*-${PY_TAG}-${PY_TAG}-*.whl" in combined_runs
    assert "expected wheel-bundled libwirelog" in combined_runs
    assert "tests/integration/test_wheel_install.py" in combined_runs
    assert "tests/integration/test_retraction_basics.py" in combined_runs


def test_publish_downloads_wheels_and_checks_artifacts_before_pypa_publish():
    steps = _workflow()["jobs"]["publish"]["steps"]
    pypa_idx = next(
        i for i, step in enumerate(steps) if "pypa/gh-action-pypi-publish" in step.get("uses", "")
    )
    gh_release_idx = next(
        i for i, step in enumerate(steps) if "softprops/action-gh-release" in step.get("uses", "")
    )
    check_idx = next(
        i
        for i, step in enumerate(steps)
        if step.get("name") == "verify release artifacts before publish"
    )
    attest_idx = next(i for i, step in enumerate(steps) if step.get("uses") == "actions/attest@v4")
    wheel_downloads = [
        (i, s)
        for i, s in enumerate(steps)
        if s.get("uses") == "actions/download-artifact@v8.0.1"
        and s.get("with", {}).get("pattern") == "wheels-*"
    ]
    assert wheel_downloads
    wheel_download_idx, wheel_download = wheel_downloads[0]
    assert wheel_download_idx < check_idx < attest_idx < pypa_idx
    assert attest_idx < gh_release_idx
    assert wheel_download["with"]["path"] == "dist"
    assert wheel_download["with"]["merge-multiple"] is True

    check_run = steps[check_idx]["run"]
    assert "dist/pyrewire-*.tar.gz" in check_run
    assert "manylinux_2_28_x86_64" in check_run
    assert "macosx_*_arm64" in check_run
    assert "win_amd64" in check_run
    for py_tag in ("cp311", "cp312", "cp313", "cp314"):
        assert py_tag in check_run


def test_publish_attestation_subject_paths_cover_wheels_and_sdist():
    steps = _workflow()["jobs"]["publish"]["steps"]
    attest_step = next(step for step in steps if step.get("uses") == "actions/attest@v4")
    subject_path = str(attest_step.get("with", {}).get("subject-path", ""))
    assert "dist/pyrewire-*.whl" in subject_path
    assert "dist/pyrewire-*.tar.gz" in subject_path


def test_release_is_not_sdist_only():
    steps = _workflow()["jobs"]["publish"]["steps"]
    download_with = [s.get("with", {}) for s in steps]
    assert any(w.get("name") == "sdist" for w in download_with)
    assert any(w.get("pattern") == "wheels-*" for w in download_with)
    assert "install_test" in _workflow()["jobs"]["publish"]["needs"]


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


def test_release_workflow_top_level_permissions_are_read_only():
    perms = _workflow().get("permissions", {})
    assert perms == {"contents": "read"}


def test_only_publish_job_has_write_and_oidc_permissions():
    jobs = _workflow()["jobs"]
    publish_perms = jobs["publish"].get("permissions", {})
    assert publish_perms == {
        "contents": "write",
        "id-token": "write",
        "attestations": "write",
    }

    for job_name in ("build_wheels", "install_test", "build_sdist"):
        assert (
            "permissions" not in jobs[job_name]
        ), f"{job_name} should inherit top-level read-only permissions"
