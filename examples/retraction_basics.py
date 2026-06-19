# SPDX-License-Identifier: Apache-2.0 OR GPL-3.0-or-later
"""Port of wirelog `examples/09-retraction-basics` to PyreWire.

Demonstrates z-set retraction semantics through `EasySession.step`:

1. Insert `friend("alice", "bob")` and `friend("bob", "alice")`.
   The recursive rule derives two `mutual` rows.
2. Add an unrelated friendship — no new `mutual` rows.
3. Remove one direction — both `mutual` rows retract symmetrically.

Drives one fixpoint `step()` per phase and prints the deltas wirelog
emitted. Requires a libwirelog that includes wirelog#852 (tagged
`> v0.41.0` — tracked in wirelog#859); older builds may emit empty
delta lists.
"""

from __future__ import annotations

from pyrewire import EasySession

SRC = """
.decl friend(a: symbol, b: symbol)
.decl mutual(a: symbol, b: symbol)
mutual(A, B) :- friend(A, B), friend(B, A).
"""


def run() -> dict[str, list[tuple]]:
    """Return the deltas from each phase, for the integration test."""
    phases: dict[str, list[tuple]] = {}
    with EasySession(SRC) as s:
        s.insert("friend", ["alice", "bob"])
        s.insert("friend", ["bob", "alice"])
        phases["phase1_mutual_emerges"] = s.step()

        s.insert("friend", ["alice", "carol"])
        phases["phase2_no_new_mutual"] = s.step()

        s.remove("friend", ["bob", "alice"])
        phases["phase3_retraction"] = s.step()
    return phases


if __name__ == "__main__":  # pragma: no cover
    for label, deltas in run().items():
        print(f"== {label} ==")
        for rel, row, diff in deltas:
            sign = "+" if diff > 0 else "-"
            print(f"{sign}{rel}{row}")
