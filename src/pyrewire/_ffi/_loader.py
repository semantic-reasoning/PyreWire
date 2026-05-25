"""libwirelog discovery, loading, and runtime version verification.

PyreWire and wirelog version independently. PyreWire declares the oldest
libwirelog version it can run against in `MINIMUM_WIRELOG_VERSION`; newer
wirelog builds, including main-branch snapshots, are accepted. When
`wirelog_version_string` is exported (the default since
semantic-reasoning/wirelog#841 landed) the reported value is checked
against that floor. Pre-#841 builds that omit the symbol cause a
`WirelogVersionUnavailableWarning` and the load proceeds with library
presence confirmed via a sentinel-symbol probe.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import os
import re
import subprocess
import sys
import warnings
from pathlib import Path

# Sentinel symbol whose presence proves the loaded library is wirelog.
# `wirelog_easy_open` is exported by every 0.x release of wirelog and is
# expected to remain so through 1.0.
_SENTINEL_SYMBOL = "wirelog_easy_open"


MINIMUM_WIRELOG_VERSION: tuple[int, int, int] = (0, 44, 0)
"""Oldest libwirelog version this PyreWire build supports.

PyreWire CI builds against a pinned wirelog release commit, so the loader
must not reject newer releases or main snapshots merely because the minor
version advanced. Older runtimes remain unsupported because they lack
symbols and parser behavior PyreWire now relies on.
"""


class WirelogVersionError(Exception):
    """Raised when libwirelog's reported version is too old for this PyreWire build."""


class WirelogVersionUnavailableWarning(UserWarning):
    """Emitted when libwirelog does not export wirelog_version_string.

    Should not fire against any wirelog build after semantic-reasoning/wirelog#841
    (resolved). Surfacing it means PyreWire is paired with a pre-fix
    libwirelog; upgrade the wirelog install.
    """


def _soname() -> str:
    if sys.platform == "darwin":  # pragma: no cover - macOS-only branch
        return "libwirelog.1.dylib"
    if sys.platform == "win32":  # pragma: no cover - Windows-only branch
        return "wirelog-1.dll"
    return "libwirelog.so.1"


def _candidate_paths() -> list[str]:
    """Return libwirelog candidate paths in priority order.

    If `$WIRELOG_LIB` is set, it is treated as an explicit override and
    no fallback candidates are tried. Otherwise the order is:

      1. wheel-bundled `<pkg>/_lib/<soname>`
      2. `pkg-config --variable=libdir wirelog` + `/<soname>`
      3. `ctypes.util.find_library('wirelog')`
    """
    out: list[str] = []
    soname = _soname()

    env = os.environ.get("WIRELOG_LIB", "").strip()
    if env:
        return [env]

    # Wheel-bundled: src/pyrewire/_lib/<soname>
    bundled = Path(__file__).resolve().parent.parent / "_lib" / soname
    out.append(str(bundled))

    try:
        result = subprocess.run(
            ["pkg-config", "--variable=libdir", "wirelog"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            out.append(str(Path(result.stdout.strip()) / soname))
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    via_ctypes = ctypes.util.find_library("wirelog")
    if via_ctypes:
        out.append(via_ctypes)

    return out


def load_libwirelog() -> ctypes.CDLL:
    """Try each candidate path; return the first that loads.

    Raises:
        OSError: if every candidate fails, with a message listing each
            attempt and the OS-level error it produced.
    """
    errors: list[str] = []
    for candidate in _candidate_paths():
        try:
            handle = ctypes.CDLL(candidate, mode=ctypes.RTLD_GLOBAL)
        except OSError as exc:
            errors.append(f"  {candidate}: {exc}")
            continue
        try:
            _ = getattr(handle, _SENTINEL_SYMBOL)
        except AttributeError:
            errors.append(
                f"  {candidate}: loaded but missing sentinel symbol "
                f"{_SENTINEL_SYMBOL!r}; not a wirelog library"
            )
            continue
        return handle

    raise OSError(
        "Could not find libwirelog. Tried (in order):\n"
        + ("\n".join(errors) if errors else "  (no candidates)")
        + "\n\nSet WIRELOG_LIB=/absolute/path/to/"
        + _soname()
        + " or install "
        "wirelog into a directory the dynamic linker searches."
    )


_PEP440_LOCAL_RE = re.compile(r"\+[A-Za-z0-9.]+$")


def _pep440_base(version: str) -> str:
    """Strip a PEP 440 local-version segment (e.g. '0.40.99+py1' -> '0.40.99')."""
    return _PEP440_LOCAL_RE.sub("", version)


def _parse_version(version: str) -> tuple[int, int, int]:
    """Parse a `MAJOR.MINOR.PATCH` (PEP 440 base) string to a tuple.

    Extra dot-separated components (e.g. wirelog dev tags) are ignored;
    only the first three numeric segments are consulted.
    """
    parts = _pep440_base(version).split(".")
    nums: list[int] = []
    for part in parts[:3]:
        try:
            nums.append(int(part))
        except ValueError:
            break
    while len(nums) < 3:
        nums.append(0)
    return nums[0], nums[1], nums[2]


def _verify_version(handle: ctypes.CDLL) -> None:
    """Reject libwirelog builds older than MINIMUM_WIRELOG_VERSION.

    Pre-#841 builds without `wirelog_version_string` emit
    `WirelogVersionUnavailableWarning` and skip the comparison.
    """
    minimum = "{}.{}.{}".format(*MINIMUM_WIRELOG_VERSION)
    try:
        fn = handle.wirelog_version_string
    except AttributeError:
        warnings.warn(
            "libwirelog does not export wirelog_version_string; cannot "
            f"verify the loaded library is at least wirelog {minimum}. "
            "Upgrade libwirelog to a post-#841 build.",
            WirelogVersionUnavailableWarning,
            stacklevel=2,
        )
        return
    fn.restype = ctypes.c_char_p
    fn.argtypes = []
    raw = fn()
    if raw is None:  # pragma: no cover - wirelog never returns NULL here
        warnings.warn(
            "wirelog_version_string returned NULL; skipping version check.",
            WirelogVersionUnavailableWarning,
            stacklevel=2,
        )
        return
    actual = _pep440_base(raw.decode())
    parsed = _parse_version(actual)
    if parsed < MINIMUM_WIRELOG_VERSION:
        raise WirelogVersionError(
            f"libwirelog version {actual!r} is older than the supported "
            f"minimum wirelog {minimum}. Install a compatible libwirelog "
            "or set WIRELOG_LIB to a supported library."
        )


LIB: ctypes.CDLL = load_libwirelog()
_verify_version(LIB)
