# SPDX-License-Identifier: Apache-2.0 OR GPL-3.0-or-later
"""Integration test against an installed PyreWire wheel (#33).

Runs in the `install_test` job of `.github/workflows/wheels.yml`
after `pip install`-ing one of the built wheels into a clean
GitHub-hosted runner. The properties asserted here are the ones a
wheel-bundling regression would silently break:

- The library is the one bundled inside `pyrewire/_lib/`, not some
  system copy that happened to be on the loader path.
- The runtime wirelog version satisfies the loader's compatibility floor.
- A non-trivial recursive datalog program produces the expected
  closure — proves the bundled binary is actually functional, not
  just present.

Example-level retraction behavior is covered by
`tests/integration/test_retraction_basics.py`.
"""

from __future__ import annotations

import os

import pytest

# This test module asserts properties that only hold when PyreWire was
# installed from a *bundled wheel* (the wheels.yml install_test job).
# Running it against the editable dev install (which loads libwirelog
# via `WIRELOG_LIB=…`) would always fail the `_lib`-path assertion.
# Set `PYREWIRE_WHEEL_INSTALL_TEST=1` in the workflow to enable.
if os.environ.get("PYREWIRE_WHEEL_INSTALL_TEST") != "1":
    pytest.skip(
        "install_test runs only against a pip-installed wheel "
        "(set PYREWIRE_WHEEL_INSTALL_TEST=1 to enable)",
        allow_module_level=True,
    )

# Imports below run only inside the wheel install_test job, so the
# loader has the bundled libwirelog available and pyrewire imports
# cleanly without `WIRELOG_LIB`.
import pyrewire  # noqa: E402
from pyrewire import BatchProgram  # noqa: E402

ANCESTOR_SRC = """
.decl parent(p: int32, c: int32)
.decl ancestor(p: int32, c: int32)

parent(1, 2).
parent(2, 3).
parent(3, 4).

ancestor(P, C) :- parent(P, C).
ancestor(P, C) :- parent(P, X), ancestor(X, C).
"""


def test_loaded_wirelog_satisfies_minimum_version():
    """The loader's version check would have raised at import time if
    this runtime were too old. Assert it loud and clear for the workflow
    log."""
    from pyrewire._ffi._loader import MINIMUM_WIRELOG_VERSION, _parse_version

    assert _parse_version(pyrewire.wirelog_version()) >= MINIMUM_WIRELOG_VERSION


def test_bundled_library_is_wheel_local():
    """The loader (#2) prefers the wheel-bundled libwirelog over any
    system copy. Confirm it actually picked the bundled one."""
    from pyrewire._ffi import LIB

    path = getattr(LIB, "_name", "")
    # The loader stores the resolved library path. The wheel-bundled
    # copy lives under `pyrewire/_lib/`.
    assert (
        "pyrewire" in path and "_lib" in path
    ), f"expected wheel-bundled libwirelog, loader chose {path!r}"


def test_recursive_closure_runs_through_bundled_library():
    """Non-trivial datalog program through the wheel-installed library
    must produce the expected closure. Proves the bundled binary is
    *functional*, not just present."""
    with BatchProgram.from_string(ANCESTOR_SRC) as bp:
        bp.optimize()
        res = bp.evaluate()
        try:
            rows = set(res.relation("ancestor"))
        finally:
            res.close()
    # The recursive ancestor rule yields all transitive pairs.
    expected = {(1, 2), (2, 3), (3, 4), (1, 3), (2, 4), (1, 4)}
    assert rows == expected, f"closure mismatch: got {sorted(rows)}"
