# SPDX-License-Identifier: Apache-2.0 OR GPL-3.0-or-later
"""Regression coverage for Dependabot configuration in this repository."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

yaml = pytest.importorskip("yaml")


def _config() -> dict[str, Any]:
    path = Path(__file__).resolve().parent.parent / ".github" / "dependabot.yml"
    assert path.is_file(), f"Dependabot config missing: {path}"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _updates_by_ecosystem() -> dict[str, dict[str, Any]]:
    updates = _config()["updates"]
    return {str(entry["package-ecosystem"]): entry for entry in updates}


def test_dependabot_has_required_ecosystems_at_repo_root():
    updates = _updates_by_ecosystem()
    assert {"github-actions", "pip"} <= set(updates)
    assert updates["github-actions"]["directory"] == "/"
    assert updates["pip"]["directory"] == "/"


def test_dependabot_uses_regular_schedules():
    for entry in _updates_by_ecosystem().values():
        interval = entry["schedule"]["interval"]
        assert interval in {"daily", "weekly", "monthly"}
