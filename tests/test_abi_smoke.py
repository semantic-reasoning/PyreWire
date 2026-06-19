# SPDX-License-Identifier: Apache-2.0 OR GPL-3.0-or-later
"""ABI smoke test: every public wirelog symbol must resolve at runtime.

The canonical manifest lives at `tests/data/wirelog_abi.txt`. When wirelog
adds or removes a public symbol the manifest must be updated in the same
PR that bumps PyreWire to a new wirelog version — this test then either
catches the drop or confirms the new symbol is present.

This is one of two test files allowed (per project convention) to reach
into `pyrewire._ffi` directly.
"""

from __future__ import annotations

from pathlib import Path

from pyrewire._ffi import LIB

_MANIFEST = Path(__file__).parent / "data" / "wirelog_abi.txt"


def _expected_symbols() -> list[str]:
    out: list[str] = []
    for line in _MANIFEST.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        out.append(s)
    return out


def test_manifest_is_non_empty():
    assert _expected_symbols(), f"manifest {_MANIFEST} is empty"


def test_every_public_symbol_resolves():
    """For every name in `tests/data/wirelog_abi.txt`, `LIB.<name>` must
    resolve to a non-null callable."""
    missing: list[str] = []
    for sym in _expected_symbols():
        try:
            fn = getattr(LIB, sym)
        except AttributeError:
            missing.append(sym)
            continue
        if fn is None:
            missing.append(sym)
    assert not missing, f"{len(missing)} public wirelog symbol(s) failed to resolve:\n" + "\n".join(
        f"  - {s}" for s in missing
    )


def test_no_duplicate_entries_in_manifest():
    syms = _expected_symbols()
    assert len(syms) == len(set(syms)), "duplicate entries in manifest"


def test_manifest_entries_match_naming_convention():
    """Every entry must start with `wirelog_`."""
    bad = [s for s in _expected_symbols() if not s.startswith("wirelog_")]
    assert not bad, f"manifest contains non-wirelog symbols: {bad}"
