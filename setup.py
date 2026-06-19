# SPDX-License-Identifier: Apache-2.0 OR GPL-3.0-or-later
"""Build shim that forces a platform-specific wheel."""

from __future__ import annotations

from setuptools import setup
from setuptools.dist import Distribution


class _BinaryDistribution(Distribution):
    """A distribution that reports extension modules are present."""

    def has_ext_modules(self) -> bool:  # noqa: D102 - self-explanatory.
        # PyreWire ships runtime-loaded shared objects, not built C
        # extension modules. This override forces a platform-specific
        # wheel tag so repair tools can run.
        return True


setup(distclass=_BinaryDistribution)
