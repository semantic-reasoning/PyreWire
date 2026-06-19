# SPDX-License-Identifier: Apache-2.0 OR GPL-3.0-or-later
"""Port of wirelog `examples/01-simple` to PyreWire.

Inline EDB facts + a single recursive rule. Uses
`BatchProgram.evaluate()` to materialise the IDB closure in one shot
because the EasySession `snapshot()` is pending the wirelog#852 tag.
"""

from __future__ import annotations

from pyrewire import BatchProgram

SRC = """
.decl parent(p: int32, c: int32)
.decl ancestor(p: int32, c: int32)

parent(1, 2).
parent(2, 3).
parent(3, 4).

ancestor(P, C) :- parent(P, C).
ancestor(P, C) :- parent(P, X), ancestor(X, C).
"""


def run() -> dict[str, list[tuple]]:
    """Return the materialised `ancestor` closure."""
    with BatchProgram.from_string(SRC) as bp:
        bp.optimize()
        res = bp.evaluate()
        try:
            return {"ancestor": res.relation("ancestor")}
        finally:
            res.close()


if __name__ == "__main__":  # pragma: no cover
    for rel, rows in run().items():
        print(f"== {rel} ==")
        for row in rows:
            print(row)
