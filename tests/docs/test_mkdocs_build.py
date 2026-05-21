"""Regression: `mkdocs build --strict` must succeed (#34).

Strict mode fails on stale cross-references caused by renamed or
removed public symbols, so this test catches doc drift as part of CI.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _mkdocs_available() -> bool:
    try:
        import material  # noqa: F401  -- mkdocs-material's import name
        import mkdocs  # noqa: F401
        import mkdocstrings  # noqa: F401
    except ImportError:
        return False
    return True


@pytest.mark.skipif(not _mkdocs_available(), reason="mkdocs not installed")
def test_mkdocs_build_strict_succeeds(tmp_path: Path):
    """`mkdocs build --strict` must succeed against the repo's docs/."""
    out_dir = tmp_path / "site"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "mkdocs",
            "build",
            "--strict",
            "--site-dir",
            str(out_dir),
        ],
        cwd=_repo_root(),
        check=True,
    )
    assert (out_dir / "index.html").is_file()
    # Clean up the in-repo `site/` that `mkdocs` may have created.
    shutil.rmtree(_repo_root() / "site", ignore_errors=True)
