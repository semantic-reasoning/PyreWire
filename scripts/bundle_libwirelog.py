# SPDX-License-Identifier: Apache-2.0 OR GPL-3.0-or-later
"""Copy the built wirelog library into `src/pyrewire/_lib` before wheel build."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def main() -> int:
    lib = os.environ.get("WIRELOG_LIB", "").strip()
    if not lib:
        print("WIRELOG_LIB is not set; cannot locate the built libwirelog", file=sys.stderr)
        return 1

    src = Path(lib)
    if not src.is_file():
        print(f"WIRELOG_LIB does not point to a file: {src}", file=sys.stderr)
        return 1

    dest_dir = Path(__file__).resolve().parent.parent / "src" / "pyrewire" / "_lib"
    dest_dir.mkdir(parents=True, exist_ok=True)

    # `shutil.copy` dereferences symlinks (e.g. libwirelog.so.1 -> ...).
    # The resulting destination file has the requested SONAME.
    shutil.copy(src, dest_dir / src.name)
    print(f"bundled {src} -> {dest_dir / src.name}")

    # Ensure Windows dependency DLLs shipped next to wirelog are included;
    # without this, `delvewheel` does not always collect non-anchor
    # dependency libraries.
    if sys.platform == "win32":
        for dll in sorted(src.parent.glob("*.dll")):
            if dll.name != src.name:
                shutil.copy(dll, dest_dir / dll.name)
                print(f"bundled dependency {dll} -> {dest_dir / dll.name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
