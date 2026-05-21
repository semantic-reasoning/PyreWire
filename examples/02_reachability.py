"""Port of wirelog `examples/02-graph-reachability` to PyreWire.

Transitive closure over a directed graph encoded as inline `edge`
facts. The `reach` IDB is computed via a recursive rule and returned
through `BatchProgram.evaluate()`.
"""

from __future__ import annotations

from pyrewire import BatchProgram

SRC = """
.decl edge(x: int32, y: int32)
.decl reach(x: int32, y: int32)

edge(1, 2). edge(2, 3). edge(3, 4). edge(4, 5).
edge(2, 5). edge(5, 6).

reach(X, Y) :- edge(X, Y).
reach(X, Y) :- edge(X, Z), reach(Z, Y).
"""


def run() -> dict[str, list[tuple]]:
    with BatchProgram.from_string(SRC) as bp:
        bp.optimize()
        res = bp.evaluate()
        try:
            return {"reach": res.relation("reach")}
        finally:
            res.close()


if __name__ == "__main__":  # pragma: no cover
    for rel, rows in run().items():
        print(f"== {rel} ==")
        for row in rows:
            print(row)
