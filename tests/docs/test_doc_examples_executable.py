"""Regression: every Python code block in `README.md` and
`docs/quickstart.md` must run cleanly (#122).

The quickstart and README examples are the first thing a new user
copies; if they reference a renamed or removed API they make the
package look broken. This module extracts each fenced ```python``` block
and executes it, mirroring `test_semantics_executable.py`.

The extractor is intentionally minimal — fenced ```python``` blocks
only, no doctest, no special syntax. Each block runs in its own
`exec()` namespace so blocks do not leak state between each other.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# If pyrewire cannot import (e.g. local libwirelog version mismatch),
# skip the whole module rather than turning every parametrized case into
# an opaque collection failure.
try:
    import pyrewire as _pyrewire  # noqa: F401
except Exception as _exc:  # noqa: BLE001
    pytest.skip(
        f"pyrewire not importable in this env: {_exc}",
        allow_module_level=True,
    )

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_DOC_FILES = [
    _REPO_ROOT / "README.md",
    _REPO_ROOT / "docs" / "quickstart.md",
]

_FENCE_RE = re.compile(r"^```python\s*$", re.MULTILINE)
_END_RE = re.compile(r"^```\s*$", re.MULTILINE)


def _extract_blocks(text: str) -> list[str]:
    """Return the source of every fenced ```python``` block."""
    blocks: list[str] = []
    pos = 0
    while True:
        start = _FENCE_RE.search(text, pos)
        if start is None:
            return blocks
        body_start = start.end() + 1  # skip the newline after ```python
        end = _END_RE.search(text, body_start)
        if end is None:
            return blocks
        blocks.append(text[body_start : end.start()])  # noqa: E203
        pos = end.end()


def _doc_pages() -> list[Path]:
    return [p for p in _DOC_FILES if p.is_file()]


_PARAMS: list[tuple[Path, int, str]] = []
for _page in _doc_pages():
    for _idx, _code in enumerate(_extract_blocks(_page.read_text(encoding="utf-8"))):
        _PARAMS.append((_page, _idx, _code))


@pytest.mark.parametrize(
    ("page", "idx", "code"),
    _PARAMS,
    ids=[f"{p.name}#{i}" for (p, i, _c) in _PARAMS],
)
def test_doc_code_block_runs(page: Path, idx: int, code: str) -> None:
    """Each documented Python block runs cleanly against the package."""
    namespace: dict[str, object] = {"__name__": "__main__"}
    exec(compile(code, str(page), "exec"), namespace)
