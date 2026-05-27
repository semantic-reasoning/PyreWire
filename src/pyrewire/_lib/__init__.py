"""Wheel-bundled shared libraries live in this package."""

from __future__ import annotations

# During wheel builds, cibuildwheel executes
# `scripts/bundle_libwirelog.py` to place `libwirelog` here before
# repair. Source distributions intentionally keep this package empty so
# they do not ship prebuilt binaries.
