# SPDX-License-Identifier: Apache-2.0 OR GPL-3.0-or-later
"""Regression coverage for the documented v1.0 support matrix."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Any

import pytest

yaml = pytest.importorskip("yaml")

PINNED_WIRELOG_SHA = "0c6e0cdaee7db069be5d8d896bb59bdcb15673e9"
SUPPORTED_PYTHONS = ["3.11", "3.12", "3.13", "3.14"]
SUPPORTED_CP_TAGS = ["cp311", "cp312", "cp313", "cp314"]
SUPPORTED_RUNNERS = ["ubuntu-24.04", "macos-15", "windows-2025-vs2026"]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (_repo_root() / path).read_text(encoding="utf-8")


def _pyproject() -> dict[str, Any]:
    return tomllib.loads(_read("pyproject.toml"))


def _workflow(path: str) -> dict[str, Any]:
    return yaml.safe_load(_read(path))


def _support_text() -> str:
    return _read("docs/support.md")


def test_support_page_is_linked_from_mkdocs_nav():
    mkdocs = _workflow("mkdocs.yml")
    assert {"Support": "support.md"} in mkdocs["nav"]


def test_readme_installation_links_support_matrix_and_python_contract():
    readme = _read("README.md")
    assert "[support matrix](docs/support.md)" in readme
    assert "CPython 3.11, 3.12, 3.13, or 3.14" in readme
    assert "3.10" not in readme


def test_support_python_matrix_matches_pyproject_and_workflows():
    pyproject = _pyproject()
    cibw_build = pyproject["tool"]["cibuildwheel"]["build"]
    classifiers = pyproject["project"]["classifiers"]
    ci_matrix = _workflow(".github/workflows/ci.yml")["jobs"]["test"]["strategy"]["matrix"]
    install_matrix = _workflow(".github/workflows/wheels.yml")["jobs"]["install_test"]["strategy"][
        "matrix"
    ]
    support = _support_text()
    readme = _read("README.md")

    assert pyproject["project"]["requires-python"] == ">=3.11"
    assert cibw_build == "cp311-* cp312-* cp313-* cp314-*"
    assert ci_matrix["python"] == SUPPORTED_PYTHONS
    assert install_matrix["python"] == SUPPORTED_PYTHONS

    for version, tag in zip(SUPPORTED_PYTHONS, SUPPORTED_CP_TAGS):
        assert f"Programming Language :: Python :: {version}" in classifiers
        assert tag in cibw_build
        assert version in support
        assert version in readme

    assert "Programming Language :: Python :: 3.10" not in classifiers
    assert "cp310" not in cibw_build
    assert "3.10" not in ci_matrix["python"]
    assert "3.10" not in install_matrix["python"]
    assert "3.10" not in support


def test_support_os_matrix_matches_workflow_and_cibuildwheel_targets():
    pyproject = _pyproject()
    wheels = _workflow(".github/workflows/wheels.yml")
    support = _support_text()

    build_matrix = wheels["jobs"]["build_wheels"]["strategy"]["matrix"]
    install_matrix = wheels["jobs"]["install_test"]["strategy"]["matrix"]
    assert build_matrix["os"] == SUPPORTED_RUNNERS
    assert install_matrix["os"] == SUPPORTED_RUNNERS

    assert pyproject["tool"]["cibuildwheel"]["linux"]["manylinux-x86_64-image"] == (
        "manylinux_2_28"
    )
    assert pyproject["tool"]["cibuildwheel"]["macos"]["archs"] == ["arm64"]
    assert pyproject["tool"]["cibuildwheel"]["windows"]["archs"] == ["AMD64"]

    for expected in (
        "manylinux_2_28",
        "x86_64",
        "ubuntu-24.04",
        "arm64",
        "macos-15",
        "win_amd64",
        "AMD64",
        "windows-2025-vs2026",
    ):
        assert expected in support

    assert "Apple Silicon only" in support
    assert re.search(r"no macOS Intel or universal2 wheel", support)


def test_support_wirelog_bundle_contract_matches_config_and_versioning():
    pyproject = _pyproject()
    support = _support_text()
    versioning = _read("docs/versioning.md")

    cibw = pyproject["tool"]["cibuildwheel"]
    assert cibw["environment"]["WIRELOG_VERSION"] == PINNED_WIRELOG_SHA
    assert cibw["linux"]["environment"]["WIRELOG_VERSION"] == PINNED_WIRELOG_SHA
    assert cibw["macos"]["environment"]["WIRELOG_VERSION"] == PINNED_WIRELOG_SHA
    assert cibw["windows"]["environment"]["WIRELOG_VERSION"] == PINNED_WIRELOG_SHA

    assert "wirelog v0.51.0" in support
    assert PINNED_WIRELOG_SHA in support
    assert "peeled SHA" in support
    assert "Wheels bundle" in versioning
    assert PINNED_WIRELOG_SHA in versioning


def test_support_documents_sdist_system_libwirelog_behavior():
    support = _support_text()
    loader = _read("src/pyrewire/_ffi/_loader.py")

    assert "Source distributions do not bundle `libwirelog`" in support
    assert "compatible system `libwirelog`" in support
    assert "minimum compatible wirelog version is >= 0.44.0" in support
    assert "`WIRELOG_LIB`" in support
    assert "explicit path" in support
    assert re.search(
        r"^MINIMUM_WIRELOG_VERSION:\s*tuple\[int, int, int\]\s*=\s*\(0,\s*44,\s*0\)",
        loader,
        re.MULTILINE,
    )


def test_security_supported_versions_match_v1_contract():
    security = _read("SECURITY.md")
    assert "| v1.0.x  | \u2713 |" in security
    assert "| < v1.0  | \u2717 |" in security
    assert "alpha" not in security.lower()
    assert "v0.1.x" not in security
