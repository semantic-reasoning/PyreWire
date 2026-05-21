#!/usr/bin/env python
"""Verify every PyreWire wheel ships libwirelog *dynamically* (#32).

Run after the wheel build matrix from #30; takes wheel paths on the
command line:

    python scripts/ci/check_dynamic_link.py wheelhouse/*.whl

Exits 0 on success, 1 (and prints offenders) when any wheel is
missing the bundled wirelog or ships a statically-linked archive.

Why: PyreWire is dual-licensed Apache-2.0 / GPL-3.0-or-later and
depends on LGPL-3.0 wirelog. LGPL permits dynamic linking from
non-LGPL code without propagating the LGPL obligation; static
linking does not. A regression that statically links wirelog would
silently change PyreWire's effective licence — this gate makes it
impossible.
"""

from __future__ import annotations

import platform
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


def _extract(wheel: Path, dest: Path) -> None:
    with zipfile.ZipFile(wheel) as zf:
        zf.extractall(dest)


def check_linux(wheel: Path) -> list[str]:
    errors: list[str] = []
    with tempfile.TemporaryDirectory() as td:
        _extract(wheel, Path(td))
        bundled = list(Path(td).rglob("libwirelog.so*"))
        if not bundled:
            errors.append(f"{wheel.name}: no libwirelog.so found in wheel")
            return errors
        for f in bundled:
            res = subprocess.run(
                ["file", str(f)],
                capture_output=True,
                text=True,
            )
            if "shared object" not in res.stdout:
                errors.append(
                    f"{wheel.name}: {f.name} is not a shared object " f"(got: {res.stdout.strip()})"
                )
    return errors


def check_macos(wheel: Path) -> list[str]:
    errors: list[str] = []
    with tempfile.TemporaryDirectory() as td:
        _extract(wheel, Path(td))
        bundled = list(Path(td).rglob("libwirelog*.dylib"))
        if not bundled:
            errors.append(f"{wheel.name}: no libwirelog dylib found")
            return errors
        for f in bundled:
            # `otool -D` prints the install_name. A static archive
            # would lack one entirely.
            res = subprocess.run(
                ["otool", "-D", str(f)],
                capture_output=True,
                text=True,
            )
            install_lines = [line for line in res.stdout.splitlines() if line.strip()]
            # Expect at least 2 lines: the file path and the install name.
            if len(install_lines) < 2:
                errors.append(
                    f"{wheel.name}: {f.name} has no install_name " "(possibly a static archive)"
                )
    return errors


def check_windows(wheel: Path) -> list[str]:
    errors: list[str] = []
    with tempfile.TemporaryDirectory() as td:
        _extract(wheel, Path(td))
        bundled = list(Path(td).rglob("wirelog*.dll"))
        if not bundled:
            errors.append(f"{wheel.name}: no wirelog DLL found")
    return errors


def check_wheel(wheel: Path) -> list[str]:
    if not wheel.exists():
        return [f"{wheel}: missing"]
    name = wheel.name.lower()
    if "linux" in name or "manylinux" in name:
        return check_linux(wheel)
    if "macosx" in name or "darwin" in name:
        return check_macos(wheel)
    if "win" in name:
        return check_windows(wheel)
    # Fall back to the current platform for `python check_dynamic_link.py
    # local.whl`-style invocations.
    system = platform.system()
    if system == "Linux":
        return check_linux(wheel)
    if system == "Darwin":
        return check_macos(wheel)
    if system == "Windows":
        return check_windows(wheel)
    return [f"{wheel}: unsupported platform/wheel tag"]


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: check_dynamic_link.py <wheel> [<wheel>...]", file=sys.stderr)
        return 2
    errors: list[str] = []
    checked = 0
    for w in argv:
        # Allow glob-style arguments — many CI shells don't expand on
        # Windows runners. `Path.glob` only accepts relative patterns,
        # so split absolute paths into anchor + pattern. If no glob
        # characters are present, treat the argument as a literal path.
        if any(c in w for c in "*?["):
            p = Path(w)
            if p.is_absolute():
                anchor = p.anchor
                rel = p.relative_to(anchor)
                matches = sorted(Path(anchor).glob(str(rel)))
            else:
                matches = sorted(Path().glob(w))
            paths = matches or []
        else:
            paths = [Path(w)]
        for path in paths:
            errors.extend(check_wheel(path))
            checked += 1
    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        return 1
    if checked == 0:
        print("no wheels matched the given paths", file=sys.stderr)
        return 1
    print(f"All {checked} wheels link wirelog dynamically.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
