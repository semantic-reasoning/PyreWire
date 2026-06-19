# SPDX-License-Identifier: Apache-2.0 OR GPL-3.0-or-later
"""Self-contained `.input` example backed by a Python IO adapter.

The upstream wirelog examples often load EDB relations from CSV files.
PyreWire can serve the same `.input` surface from Python by registering
an adapter that returns int64 rows to wirelog.
"""

from __future__ import annotations

from pyrewire import BatchProgram, IOContext, register_adapter, unregister_adapter

SCHEME = "pyrewire_example_edges"

SRC = f"""
.decl edge(x: int32, y: int32)
.input edge(io="{SCHEME}", source="inline")

.decl reach(x: int32, y: int32)
reach(X, Y) :- edge(X, Y).
reach(X, Y) :- edge(X, Z), reach(Z, Y).
"""


def _register_edges_adapter() -> None:
    unregister_adapter(SCHEME)

    @register_adapter(SCHEME, description="PyreWire example edge rows")
    class _Edges:
        def validate(self, ctx: IOContext) -> None:
            if ctx.relation_name != "edge" or ctx.num_cols != 2:
                raise ValueError("edge adapter expects edge/2")

        def read(self, ctx: IOContext) -> list[list[int]]:
            return [
                [1, 2],
                [2, 3],
                [3, 4],
                [2, 5],
            ]


def run() -> dict[str, list[tuple]]:
    """Load `edge` through the adapter and return the transitive closure."""
    _register_edges_adapter()
    try:
        with BatchProgram.from_string(SRC) as bp:
            bp.optimize()
            bp.load_input_files()
            res = bp.evaluate()
            try:
                return {"reach": res.relation("reach")}
            finally:
                res.close()
    finally:
        unregister_adapter(SCHEME)


if __name__ == "__main__":  # pragma: no cover
    for rel, rows in run().items():
        print(f"== {rel} ==")
        for row in rows:
            print(row)
