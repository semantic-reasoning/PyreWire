"""Regression: every Python code block in `docs/semantics/*.md` must run.

Pages annotated with `# expected: <exception>` are allowed to raise
the named exception; everything else must complete cleanly.

The extractor is intentionally minimal — fenced ```python``` blocks
only, no doctest, no special syntax. Each block runs in its own
`exec()` namespace so blocks don't leak state between each other.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

# If pyrewire cannot import (e.g. local libwirelog version mismatch),
# skip the entire semantics-block test module rather than turning every
# parametrized case into an opaque collection failure.
try:
    import pyrewire as _pyrewire  # noqa: F401
except Exception as _exc:  # noqa: BLE001
    pytest.skip(
        f"pyrewire not importable in this env: {_exc}",
        allow_module_level=True,
    )

_SEMANTICS_DIR = Path(__file__).resolve().parent.parent.parent / "docs" / "semantics"

_FENCE_RE = re.compile(r"^```python\s*$", re.MULTILINE)
_END_RE = re.compile(r"^```\s*$", re.MULTILINE)
# Only `# expected: <SomeCamelCaseExceptionName>` activates the
# "must raise" path; anything else (`# expected: row stays …`) is
# free-form commentary the test ignores.
_EXPECTED_RE = re.compile(r"^\s*#\s*expected:\s*([A-Z][A-Za-z0-9_]*)\s*$", re.MULTILINE)


def _extract_blocks(text: str) -> list[tuple[str, str | None]]:
    """Return (code, expected_exception_name_or_None) for every
    fenced ```python``` block."""
    blocks: list[tuple[str, str | None]] = []
    pos = 0
    while True:
        start = _FENCE_RE.search(text, pos)
        if start is None:
            return blocks
        body_start = start.end() + 1  # skip the newline after ```python
        end = _END_RE.search(text, body_start)
        if end is None:
            return blocks
        code = text[body_start : end.start()]  # noqa: E203
        m = _EXPECTED_RE.search(code)
        expected = m.group(1) if m else None
        blocks.append((code, expected))
        pos = end.end()


def _semantics_pages() -> list[Path]:
    if not _SEMANTICS_DIR.is_dir():
        return []
    return sorted(_SEMANTICS_DIR.glob("*.md"))


def _block_param_id(page: Path, idx: int) -> str:
    return f"{page.name}#{idx}"


_PARAMS: list[tuple[Path, int, str, str | None]] = []
for _page in _semantics_pages():
    for _idx, (_code, _expected) in enumerate(_extract_blocks(_page.read_text())):
        _PARAMS.append((_page, _idx, _code, _expected))


@pytest.mark.parametrize(
    ("page", "idx", "code", "expected"),
    _PARAMS,
    ids=[_block_param_id(p, i) for (p, i, _c, _e) in _PARAMS],
)
def test_semantics_code_block_runs(page: Path, idx: int, code: str, expected: str | None) -> None:
    """Each block either runs cleanly or raises the documented exception."""
    namespace: dict[str, object] = {"__name__": "__main__"}
    if expected is None:
        exec(compile(code, str(page), "exec"), namespace)
        return
    expected_cls = _resolve_exception(expected)
    try:
        exec(compile(code, str(page), "exec"), namespace)
    except expected_cls:
        return
    pytest.fail(f"{page.name} block #{idx} was expected to raise {expected!r} but did not")


def _resolve_exception(name: str) -> type[BaseException]:
    # Local import so the test file imports cleanly even if pyrewire's
    # error module changes shape.
    from pyrewire._core import errors  # noqa: WPS433

    cls = getattr(errors, name, None)
    if isinstance(cls, type) and issubclass(cls, BaseException):
        return cls
    # Fall back to stdlib (ValueError, TypeError, etc.).
    builtin = getattr(sys.modules["builtins"], name, None)
    if isinstance(builtin, type) and issubclass(builtin, BaseException):
        return builtin
    raise LookupError(f"unknown exception name in docs: {name!r}")
