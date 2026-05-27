"""Regression coverage for the documented v1.0 public API policy."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import pyrewire

yaml = pytest.importorskip("yaml")

POLICY_PATH = "docs/api-stability.md"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (_repo_root() / path).read_text(encoding="utf-8")


def _policy_text() -> str:
    return _read(POLICY_PATH)


def _stable_boundary_names() -> set[str]:
    text = _policy_text()
    stable_section = text.split("## Stable public boundary", 1)[1].split(
        "## Non-public boundary", 1
    )[0]
    return set(re.findall(r"^- `([^`]+)`$", stable_section, re.MULTILINE))


def test_policy_declares_all_as_stable_public_boundary():
    text = _policy_text()

    assert "`pyrewire.__all__` as the stable public import boundary" in text
    assert "v1 stable public API" in text
    assert _stable_boundary_names() == set(pyrewire.__all__)

    documented_names = set(re.findall(r"`([^`]+)`", text))
    for name in pyrewire.__all__:
        assert name in documented_names


def test_policy_groups_exported_names_by_stable_category():
    text = _policy_text()

    expected_sections = [
        "### Sessions",
        "### Batch and result",
        "### Program, schema, and introspection",
        "### Async wrappers",
        "### IO adapters",
        "### Compounds",
        "### IR wrapper and enums",
        "### Exported enums",
        "### Exported errors",
        "### Helpers and utilities",
    ]

    for section in expected_sections:
        assert section in text


def test_policy_excludes_private_and_raw_ctypes_boundaries():
    text = _policy_text()

    assert "## Non-public boundary" in text
    for private_name in ("pyrewire._ffi", "pyrewire._core", "pyrewire._lib"):
        assert f"`{private_name}`" in text
        assert private_name not in pyrewire.__all__

    assert "raw `ctypes` handles" in text
    assert "private attributes" in text
    assert "non-exported internals" in text


def test_policy_documents_deprecation_and_minor_release_compatibility():
    text = _policy_text()

    assert "`DeprecationWarning`" in text
    assert "at least one minor release" in text
    assert "major releases except urgent security or correctness cases" in text

    for allowed_addition in (
        "new APIs",
        "optional parameters",
        "enum members",
        "exception subclasses",
    ):
        assert allowed_addition in text


def test_policy_is_linked_from_nav_and_project_docs():
    mkdocs = yaml.safe_load(_read("mkdocs.yml"))
    assert {"API stability": "api-stability.md"} in mkdocs["nav"]

    readme = _read("README.md")
    index = _read("docs/index.md")

    assert "[API stability policy](docs/api-stability.md)" in readme
    assert "[API stability](api-stability.md)" in index
