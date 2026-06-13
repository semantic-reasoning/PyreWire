"""Regression coverage for the documented PyreWire/wirelog compatibility contract."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

# The wirelog ref the current release bundles and validates against.
PINNED_WIRELOG_SHA = "0c6e0cdaee7db069be5d8d896bb59bdcb15673e9"
# Historical pins kept frozen in the compatibility table, one per release.
WIRELOG_SHA_100 = "272edf3a24b25676f12c4b843d55510f5048dd2f"
WIRELOG_SHA_101 = PINNED_WIRELOG_SHA


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (_repo_root() / path).read_text(encoding="utf-8")


def _versioning_row(version: str) -> list[str]:
    pattern = re.compile(rf"^\|\s*`{re.escape(version)}`\s*\|(.+)\|$", re.MULTILINE)
    match = pattern.search(_read("docs/versioning.md"))
    assert match is not None, f"docs/versioning.md missing PyreWire {version} row"
    return [cell.strip() for cell in match.group(1).split("|")]


def test_versioning_documents_100_wirelog_pin_and_runtime_floor():
    minimum, validated_ref, notes = _versioning_row("1.0.0")

    assert minimum == "`0.44.0`"
    assert validated_ref == f"`{WIRELOG_SHA_100}`"
    assert "v0.50.0" in notes
    assert "runtime minimum remains `0.44.0`" in notes
    assert "peeled tag SHA" in notes


def test_versioning_documents_101_wirelog_pin_and_runtime_floor():
    minimum, validated_ref, notes = _versioning_row("1.0.1")

    assert minimum == "`0.44.0`"
    assert validated_ref == f"`{WIRELOG_SHA_101}`"
    assert "v0.51.0" in notes
    assert "runtime minimum remains `0.44.0`" in notes
    assert "peeled tag SHA" in notes


def test_versioning_explains_sdist_and_wheel_wirelog_behavior():
    text = _read("docs/versioning.md")

    assert "Source distributions" in text
    assert "do not ship a wirelog binary" in text
    assert "source installs" in text
    assert "loader check" in text
    assert "Wheels bundle" in text
    assert "validated ref" in text


def test_wirelog_pins_and_loader_floor_match_current_contract():
    pyproject = tomllib.loads(_read("pyproject.toml"))
    ci = yaml.safe_load(_read(".github/workflows/ci.yml"))
    loader = _read("src/pyrewire/_ffi/_loader.py")

    ci_wirelog_version = ci["jobs"]["test"]["env"]["WIRELOG_VERSION"]
    assert "vars.WIRELOG_VERSION" in ci_wirelog_version
    assert PINNED_WIRELOG_SHA in ci_wirelog_version
    assert "68eb9c" not in ci_wirelog_version

    cibw = pyproject["tool"]["cibuildwheel"]
    assert cibw["environment"]["WIRELOG_VERSION"] == PINNED_WIRELOG_SHA
    assert cibw["linux"]["environment"]["WIRELOG_VERSION"] == PINNED_WIRELOG_SHA
    assert cibw["macos"]["environment"]["WIRELOG_VERSION"] == PINNED_WIRELOG_SHA
    assert cibw["windows"]["environment"]["WIRELOG_VERSION"] == PINNED_WIRELOG_SHA

    assert re.search(
        r"^MINIMUM_WIRELOG_VERSION:\s*tuple\[int, int, int\]\s*=\s*\(0,\s*44,\s*0\)",
        loader,
        re.MULTILINE,
    )
