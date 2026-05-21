"""PyreWire-flavoured port of the spirit of wirelog
`examples/12-snapshot-vs-delta`.

Compares two ways of getting the same IDB closure:

1. `BatchProgram.evaluate()` — one-shot pipeline, returns a `Result`.
2. `Session.preview_inline_facts()` — peek at inline EDB rows.

The original wirelog example contrasts snapshot vs delta, which on the
PyreWire side maps to `BatchProgram` vs the (forthcoming) EasySession
incremental mode. The latter ships when wirelog cuts a tag containing
wirelog#852 (tracked in wirelog#859); until then, this port uses the
BatchProgram + Session pairing to demonstrate the high-level shape.
"""

from __future__ import annotations

from pyrewire import BatchProgram, Program, Session

SRC = """
.decl edge(x: int32, y: int32)
.decl reach(x: int32)

edge(1, 2). edge(2, 3). edge(3, 4).

reach(X) :- edge(X, _).
"""


def run() -> dict[str, list[tuple]]:
    # Batch path: derive the IDB closure in one shot.
    with BatchProgram.from_string(SRC) as bp:
        bp.optimize()
        res = bp.evaluate()
        try:
            batch_reach = res.relation("reach")
        finally:
            res.close()

    # Session path: inspect the inline EDB without computing the IDB.
    prog = Program.from_string(SRC)
    with Session(prog) as s:
        edge_rows = s.preview_inline_facts("edge")

    return {"batch_reach": batch_reach, "session_edge": edge_rows}


if __name__ == "__main__":  # pragma: no cover
    for rel, rows in run().items():
        print(f"== {rel} ==")
        for row in rows:
            print(row)
