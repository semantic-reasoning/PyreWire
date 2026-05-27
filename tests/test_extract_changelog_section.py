from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "ci" / "extract_changelog_section.py"

spec = importlib.util.spec_from_file_location("extract_changelog_section", SCRIPT)
assert spec is not None
extract_changelog_section = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(extract_changelog_section)


def test_extracts_requested_section_only():
    changelog = """# Changelog

## [Unreleased]

### Changed
- future work

## [1.0.0] - 2026-05-27

### Added
- release note

## [0.41.0] - 2026-05-21

### Added
- older note
"""

    section = extract_changelog_section.extract_section(changelog, "1.0.0")

    assert section.startswith("## [1.0.0] - 2026-05-27")
    assert "- release note" in section
    assert "[Unreleased]" not in section
    assert "[0.41.0]" not in section


def test_missing_section_fails_clearly(tmp_path: Path):
    changelog = tmp_path / "CHANGELOG.md"
    output = tmp_path / "release-notes.md"
    changelog.write_text("## [Unreleased]\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(changelog), "1.0.0", str(output)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "ERROR: CHANGELOG.md has no section for version '1.0.0'" in result.stderr
    assert not output.exists()


def test_cli_writes_release_notes_file(tmp_path: Path):
    changelog = tmp_path / "CHANGELOG.md"
    output = tmp_path / "notes" / "release-notes.md"
    changelog.write_text(
        """# Changelog

## [1.0.0] - 2026-05-27

### Added
- release note

## [0.41.0] - 2026-05-21
- older note
""",
        encoding="utf-8",
    )

    subprocess.run(
        [sys.executable, str(SCRIPT), str(changelog), "1.0.0", str(output)],
        check=True,
    )

    assert output.read_text(encoding="utf-8") == (
        "## [1.0.0] - 2026-05-27\n\n### Added\n- release note\n"
    )
