# SPDX-License-Identifier: Apache-2.0 OR GPL-3.0-or-later
"""Every Python source file must carry an SPDX license identifier.

PyreWire is dual-licensed (Apache-2.0 OR GPL-3.0-or-later); pyproject.toml
declares this at the package level, but per-file SPDX tags are what make the
license machine-discoverable (REUSE/SPDX tooling, downstream redistribution).
This contract test fails the build if any source file is missing the tag or
declares a different expression, so the headers cannot silently drift.
"""

from __future__ import annotations

from pathlib import Path

import pytest

SPDX_TAG = "SPDX-License-Identifier: Apache-2.0 OR GPL-3.0-or-later"

_REPO_ROOT = Path(__file__).resolve().parent.parent

# Source roots that ship or build the project. A filesystem walk from the repo
# root would also sweep build artifacts (build/, dist/, *.egg-info, .venv), so
# enumerate the source trees explicitly.
_SOURCE_ROOTS = ("src", "tests", "examples", "scripts")
_TOP_LEVEL_FILES = ("setup.py",)


def _python_sources() -> list[Path]:
    files: list[Path] = []
    for root in _SOURCE_ROOTS:
        files.extend((_REPO_ROOT / root).rglob("*.py"))
    for name in _TOP_LEVEL_FILES:
        path = _REPO_ROOT / name
        if path.is_file():
            files.append(path)
    return sorted(files)


def test_source_files_discovered():
    # Guard against the glob silently matching nothing (e.g. a moved tree),
    # which would make the per-file test vacuously pass.
    assert len(_python_sources()) >= 50


@pytest.mark.parametrize(
    "path",
    _python_sources(),
    ids=lambda p: str(p.relative_to(_REPO_ROOT)),
)
def test_file_has_spdx_identifier(path: Path):
    # SPDX must appear in the header block (after an optional shebang),
    # not buried somewhere in the body.
    head = path.read_text(encoding="utf-8").splitlines()[:5]
    assert any(SPDX_TAG in line for line in head), (
        f"{path.relative_to(_REPO_ROOT)} is missing the SPDX header "
        f"'# {SPDX_TAG}'"
    )
