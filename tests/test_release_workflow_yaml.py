"""Regression: `.github/workflows/release.yml` keeps the required steps (#37).

A release pipeline must:
- trigger on `v*` tags;
- verify the tag matches the `pyproject.toml` version;
- build and install-test wheels in the release workflow;
- publish only after release-local wheels and sdist are verified;
- publish to TestPyPI and PyPI via separate trusted publishing identities;
- create a GitHub Release.

If a future refactor accidentally drops any of these, this test fails
loudly. We parse the YAML rather than grep so re-ordering or renaming
keys (where semantically equivalent) is allowed.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

yaml = pytest.importorskip("yaml")

skip_on_windows = pytest.mark.skipif(
    sys.platform == "win32",
    reason="release publish artifact verification is a bash script run on Ubuntu",
)


def _workflow() -> dict[str, Any]:
    path = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "release.yml"
    assert path.is_file(), f"release workflow missing: {path}"
    return yaml.safe_load(path.read_text())


def _on_block() -> dict[str, Any]:
    wf = _workflow()
    on = wf.get("on") or wf.get(True)  # PyYAML sometimes parses "on:" as True
    assert isinstance(on, dict), "missing `on:` block"
    return on


def _publish_artifact_verify_script() -> str:
    steps = _workflow()["jobs"]["publish_pypi"]["steps"]
    return next(
        step["run"]
        for step in steps
        if step.get("name") == "verify release artifacts before publish"
    )


def _publish_steps(job_name: str) -> list[dict[str, Any]]:
    return _workflow()["jobs"][job_name]["steps"]


def _step_index(
    steps: list[dict[str, Any]], *, name: str | None = None, uses: str | None = None
) -> int:
    for i, step in enumerate(steps):
        if name is not None and step.get("name") == name:
            return i
        if uses is not None and uses in step.get("uses", ""):
            return i
    raise AssertionError(f"missing step name={name!r} uses={uses!r}")


def _write_complete_release_artifacts(dist: Path) -> None:
    dist.mkdir()
    (dist / "pyrewire-1.0.0.tar.gz").touch()
    for py_tag in ("cp311", "cp312", "cp313", "cp314"):
        (
            dist
            / (
                f"pyrewire-1.0.0-{py_tag}-{py_tag}-"
                "manylinux2014_x86_64.manylinux_2_17_x86_64."
                "manylinux_2_28_x86_64.whl"
            )
        ).touch()
        (dist / f"pyrewire-1.0.0-{py_tag}-{py_tag}-macosx_15_0_arm64.whl").touch()
        (dist / f"pyrewire-1.0.0-{py_tag}-{py_tag}-win_amd64.whl").touch()


def test_triggers_on_v_tags():
    push = _on_block().get("push")
    tags = (push or {}).get("tags") or []
    assert any(t.startswith("v") for t in tags), f"release must trigger on v* tags, got {tags}"


def test_workflow_dispatch_publish_testpypi_input_is_boolean_default_false():
    workflow_dispatch = _on_block().get("workflow_dispatch") or {}
    inputs = workflow_dispatch.get("inputs") or {}
    publish_testpypi = inputs.get("publish-testpypi") or {}

    assert publish_testpypi
    assert publish_testpypi.get("type") == "boolean"
    assert publish_testpypi.get("default") is False
    assert publish_testpypi.get("required") is False
    assert "testpypi" in publish_testpypi.get("description", "").lower()
    assert "publish" in publish_testpypi.get("description", "").lower()


def test_has_publish_jobs_with_ubuntu_and_explicit_environments():
    wf = _workflow()
    assert "ubuntu" in str(wf["jobs"]["publish_testpypi"].get("runs-on", "")).lower()
    assert "ubuntu" in str(wf["jobs"]["publish_pypi"].get("runs-on", "")).lower()
    assert wf["jobs"]["publish_testpypi"].get("environment") == "testpypi"
    assert wf["jobs"]["publish_pypi"].get("environment") == "pypi"


def test_release_workflow_has_build_install_publish_dag():
    jobs = _workflow()["jobs"]
    assert {
        "build_wheels",
        "install_test",
        "build_sdist",
        "publish_testpypi",
        "publish_pypi",
    } <= set(jobs)

    assert jobs["install_test"].get("needs") == "build_wheels" or "build_wheels" in (
        jobs["install_test"].get("needs") or []
    )
    for job_name in ("publish_testpypi", "publish_pypi"):
        publish_needs = jobs[job_name].get("needs") or []
        assert publish_needs == ["install_test", "build_sdist"]


def test_release_workflow_has_verify_step():
    """A step whose `name` mentions tag/version verification must exist."""
    jobs = _workflow()["jobs"].values()
    names = [s.get("name", "").lower() for job in jobs for s in job.get("steps", [])]
    assert any(
        "verify" in n and "tag" in n for n in names
    ), "release workflow must include a tag-vs-pyproject version check"


def test_publish_step_uses_pypa_action():
    for job_name in ("publish_testpypi", "publish_pypi"):
        uses = [s.get("uses", "") for s in _publish_steps(job_name)]
        assert any(
            "pypa/gh-action-pypi-publish" in u for u in uses
        ), f"{job_name} must publish through pypa/gh-action-pypi-publish"


def test_download_wheels_uses_node24_artifact_action():
    for job_name in ("publish_testpypi", "publish_pypi"):
        uses = [s.get("uses", "") for s in _publish_steps(job_name)]
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

    assert jobs["publish_testpypi"]["needs"] == ["install_test", "build_sdist"]
    assert jobs["publish_pypi"]["needs"] == ["install_test", "build_sdist"]
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


def test_pypi_publish_downloads_wheels_and_checks_artifacts_before_publish_and_release():
    steps = _publish_steps("publish_pypi")
    pypa_prod_idx = _step_index(steps, name="publish to PyPI (trusted publishing)")
    gh_release_idx = _step_index(steps, uses="softprops/action-gh-release")
    check_idx = _step_index(steps, name="verify release artifacts before publish")
    attest_idx = _step_index(steps, uses="actions/attest@v4")
    wheel_downloads = [
        (i, s)
        for i, s in enumerate(steps)
        if s.get("uses") == "actions/download-artifact@v8.0.1"
        and s.get("with", {}).get("pattern") == "wheels-*"
    ]
    assert wheel_downloads
    wheel_download_idx, wheel_download = wheel_downloads[0]
    assert wheel_download_idx < check_idx < attest_idx < pypa_prod_idx
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


@skip_on_windows
def test_publish_artifact_verify_accepts_auditwheel_linux_multi_platform_tags(tmp_path):
    _write_complete_release_artifacts(tmp_path / "dist")

    subprocess.run(
        ["bash", "-c", _publish_artifact_verify_script()],
        cwd=tmp_path,
        check=True,
    )


@skip_on_windows
def test_publish_artifact_verify_rejects_duplicate_linux_wheel(tmp_path):
    dist = tmp_path / "dist"
    _write_complete_release_artifacts(dist)
    (
        dist
        / (
            "pyrewire-1.0.0.post1-cp311-cp311-"
            "manylinux2014_x86_64.manylinux_2_17_x86_64."
            "manylinux_2_28_x86_64.whl"
        )
    ).touch()

    result = subprocess.run(
        ["bash", "-c", _publish_artifact_verify_script()],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "expected exactly one wheel matching" in result.stdout
    assert "manylinux_2_28_x86_64.whl, found 2" in result.stdout


def test_publish_has_manual_testpypi_step_with_explicit_gate_and_repository_url():
    job = _workflow()["jobs"]["publish_testpypi"]
    steps = job["steps"]
    step = next(s for s in steps if s.get("name") == "publish to TestPyPI (trusted publishing)")
    job_if = str(job.get("if", ""))
    assert job.get("environment") == "testpypi"
    assert step.get("uses") == "pypa/gh-action-pypi-publish@release/v1"
    assert step.get("with", {}).get("repository-url") == "https://test.pypi.org/legacy/"
    assert "workflow_dispatch" in job_if
    assert "publish-testpypi" in job_if
    assert "github.event_name" in job_if
    assert "if" not in step


def test_testpypi_publish_downloads_wheels_and_runs_after_verify_and_attest_steps():
    steps = _publish_steps("publish_testpypi")
    check_idx = _step_index(steps, name="verify release artifacts before publish")
    attest_idx = _step_index(steps, uses="actions/attest@v4")
    testpypi_idx = _step_index(steps, name="publish to TestPyPI (trusted publishing)")
    wheel_download_idx = next(
        i
        for i, step in enumerate(steps)
        if step.get("uses") == "actions/download-artifact@v8.0.1"
        and step.get("with", {}).get("pattern") == "wheels-*"
    )

    assert wheel_download_idx < check_idx < attest_idx < testpypi_idx


def test_production_pypi_publish_is_gated_to_tag_push_and_not_testpypi():
    job = _workflow()["jobs"]["publish_pypi"]
    steps = job["steps"]
    step = next(s for s in steps if s.get("name") == "publish to PyPI (trusted publishing)")
    assert job.get("if") == "github.event_name == 'push' && startsWith(github.ref, 'refs/tags/v')"
    assert job.get("environment") == "pypi"
    assert "if" not in step
    assert "repository-url" not in (step.get("with") or {})


def test_publish_attestation_subject_paths_cover_wheels_and_sdist():
    for job_name in ("publish_testpypi", "publish_pypi"):
        steps = _publish_steps(job_name)
        attest_step = next(step for step in steps if step.get("uses") == "actions/attest@v4")
        subject_path = str(attest_step.get("with", {}).get("subject-path", ""))
        assert "dist/pyrewire-*.whl" in subject_path
        assert "dist/pyrewire-*.tar.gz" in subject_path


def test_release_is_not_sdist_only():
    for job_name in ("publish_testpypi", "publish_pypi"):
        steps = _publish_steps(job_name)
        download_with = [s.get("with", {}) for s in steps]
        assert any(w.get("name") == "sdist" for w in download_with)
        assert any(w.get("pattern") == "wheels-*" for w in download_with)
        assert "install_test" in _workflow()["jobs"][job_name]["needs"]


def test_creates_github_release():
    steps = _publish_steps("publish_pypi")
    uses = [s.get("uses", "") for s in steps]
    assert any(
        "softprops/action-gh-release" in u for u in uses
    ), "release workflow must create a GitHub Release"
    release_step = next(
        step for step in steps if "softprops/action-gh-release" in step.get("uses", "")
    )
    assert "if" not in release_step
    assert not any(
        "softprops/action-gh-release" in s.get("uses", "")
        for s in _publish_steps("publish_testpypi")
    )


def test_github_release_uses_extracted_changelog_section():
    steps = _publish_steps("publish_pypi")
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


def test_release_notes_extraction_is_gated_to_tag_push():
    job = _workflow()["jobs"]["publish_pypi"]
    steps = job["steps"]
    extract_step = next(
        step for step in steps if step.get("name") == "extract GitHub Release notes"
    )
    assert job.get("if") == "github.event_name == 'push' && startsWith(github.ref, 'refs/tags/v')"
    assert "if" not in extract_step


def test_release_workflow_top_level_permissions_are_read_only():
    perms = _workflow().get("permissions", {})
    assert perms == {"contents": "read"}


def test_publish_jobs_have_least_privilege_write_and_oidc_permissions():
    jobs = _workflow()["jobs"]
    assert jobs["publish_testpypi"].get("permissions", {}) == {
        "id-token": "write",
        "attestations": "write",
    }
    assert jobs["publish_pypi"].get("permissions", {}) == {
        "contents": "write",
        "id-token": "write",
        "attestations": "write",
    }

    for job_name in ("build_wheels", "install_test", "build_sdist"):
        assert (
            "permissions" not in jobs[job_name]
        ), f"{job_name} should inherit top-level read-only permissions"
