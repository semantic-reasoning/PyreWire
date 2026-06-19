# SPDX-License-Identifier: Apache-2.0 OR GPL-3.0-or-later
"""Port of wirelog `examples/10-recursive-under-update` to PyreWire.

Demonstrates that wirelog correctly maintains a RECURSIVE rule under
insert/remove/re-insert. A 4-node chain a->b->c->d is built (step 1),
edge(b,c) is retracted (step 2), then re-inserted (step 3). The
`reach` transitive closure is recomputed incrementally; each phase
returns the step()'s delta list.

Requires a libwirelog that includes wirelog#852 (tagged `> v0.41.0` —
tracked in wirelog#859); older builds may emit empty delta lists.
"""

from __future__ import annotations

from pyrewire import EasySession

SRC = """
.decl edge(x: symbol, y: symbol)
.decl reach(x: symbol, y: symbol)
reach(X, Y) :- edge(X, Y).
reach(X, Z) :- reach(X, Y), edge(Y, Z).
"""


def run() -> dict[str, list[tuple]]:
    """Drive three steps and return the deltas emitted in each."""
    phases: dict[str, list[tuple]] = {}
    with EasySession(SRC) as s:
        s.insert_sym("edge", "a", "b")
        s.insert_sym("edge", "b", "c")
        s.insert_sym("edge", "c", "d")
        phases["phase1_insert_chain"] = s.step()

        s.remove_sym("edge", "b", "c")
        phases["phase2_remove_bc"] = s.step()

        s.insert_sym("edge", "b", "c")
        phases["phase3_reinsert_bc"] = s.step()
    return phases


if __name__ == "__main__":  # pragma: no cover
    for label, deltas in run().items():
        print(f"== {label} ==")
        for rel, row, diff in deltas:
            sign = "+" if diff > 0 else "-"
            print(f"{sign}{rel}{row}")
