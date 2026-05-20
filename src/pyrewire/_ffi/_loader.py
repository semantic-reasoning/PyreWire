"""libwirelog discovery, loading, and runtime version verification.

When `wirelog_version_string` is exported (the default since
semantic-reasoning/wirelog#841 landed), the loader verifies that its
value matches `pyrewire.__version__` (PEP 440 local-version segment
stripped). The pre-#841 fallback path is kept for forward-compatibility:
older wirelog builds that omit the symbol cause a
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


class WirelogVersionError(Exception):
    """Raised when libwirelog's reported version disagrees with pyrewire.__version__."""


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

    The order is:
      1. `$WIRELOG_LIB` (absolute path)
      2. wheel-bundled `<pkg>/_lib/<soname>`
      3. `pkg-config --variable=libdir wirelog` + `/<soname>`
      4. `ctypes.util.find_library('wirelog')`
    """
    out: list[str] = []
    soname = _soname()

    env = os.environ.get("WIRELOG_LIB", "").strip()
    if env:
        out.append(env)

    # Wheel-bundled: src/pyrewire/_lib/<soname>
    bundled = Path(__file__).resolve().parent.parent / "_lib" / soname
    out.append(str(bundled))

    try:
        result = subprocess.run(
            ["pkg-config", "--variable=libdir", "wirelog"],
            capture_output=True, text=True, timeout=5,
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
        + "\n\nSet WIRELOG_LIB=/absolute/path/to/" + _soname() + " or install "
        "wirelog into a directory the dynamic linker searches."
    )


_PEP440_LOCAL_RE = re.compile(r"\+[A-Za-z0-9.]+$")


def _pep440_base(version: str) -> str:
    """Strip a PEP 440 local-version segment (e.g. '0.40.99+py1' -> '0.40.99')."""
    return _PEP440_LOCAL_RE.sub("", version)


def _verify_version(handle: ctypes.CDLL) -> None:
    """Compare libwirelog's reported version against `pyrewire.__version__`.

    Pre-#841 builds without `wirelog_version_string` emit
    `WirelogVersionUnavailableWarning` and skip the comparison.
    """
    from pyrewire import __version__

    expected = _pep440_base(__version__)
    try:
        fn = handle.wirelog_version_string
    except AttributeError:
        warnings.warn(
            "libwirelog does not export wirelog_version_string; cannot "
            f"verify the loaded library matches pyrewire {expected!r}. "
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
    if actual != expected:
        raise WirelogVersionError(
            f"libwirelog version {actual!r} does not match "
            f"pyrewire version {expected!r}. PyreWire follows wirelog's "
            "versioning verbatim; install matching versions or set "
            "WIRELOG_LIB to the correct library."
        )


LIB: ctypes.CDLL = load_libwirelog()
_verify_version(LIB)
