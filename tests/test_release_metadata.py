"""Regression tests for PyreWire release metadata (#121)."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _read(path: str) -> str:
    return (_repo_root() / path).read_text(encoding="utf-8")


def _pyproject() -> dict[str, object]:
    return tomllib.loads(_read("pyproject.toml"))


def _runtime_version_literal() -> str:
    match = re.search(
        r'^__version__\s*=\s*"([^"]+)"', _read("src/pyrewire/__init__.py"), re.MULTILINE
    )
    assert match is not None, "src/pyrewire/__init__.py has no __version__ literal"
    return match.group(1)


def test_project_and_runtime_versions_are_100():
    assert _pyproject()["project"]["version"] == "1.0.0"
    assert _runtime_version_literal() == "1.0.0"


def test_project_classifiers_mark_stable_python_311_through_314():
    classifiers = _pyproject()["project"]["classifiers"]

    assert "Development Status :: 5 - Production/Stable" in classifiers
    assert "Development Status :: 3 - Alpha" not in classifiers

    for version in ("3.11", "3.12", "3.13", "3.14"):
        assert f"Programming Language :: Python :: {version}" in classifiers


def test_security_policy_tracks_v1_stable_support_only():
    security = _read("SECURITY.md")

    assert "| v1.0.x  | ✓ |" in security
    assert "alpha" not in security.lower()
    assert "v0.1.x" not in security
