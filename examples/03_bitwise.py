"""Port of wirelog `examples/03-bitwise-operations` to PyreWire.

Demonstrates wirelog's built-in bitwise functors: `band` / `bor` /
`bxor` / `bnot` / `bshl` / `bshr`. The host supplies operand pairs
and the engine derives every per-pair result.
"""

from __future__ import annotations

from pyrewire import BatchProgram

SRC = """
.decl ops(a: int32, b: int32)
.decl result(a: int32, b: int32, kind: symbol, v: int64)

ops(12, 10).
ops(255, 1).
ops(8, 3).

result(A, B, "and", band(A, B)) :- ops(A, B).
result(A, B, "or", bor(A, B))  :- ops(A, B).
result(A, B, "xor", bxor(A, B)) :- ops(A, B).
result(A, B, "shl", bshl(A, B)) :- ops(A, B).
result(A, B, "shr", bshr(A, B)) :- ops(A, B).
"""


def run() -> dict[str, list[tuple]]:
    with BatchProgram.from_string(SRC) as bp:
        bp.optimize()
        res = bp.evaluate()
        try:
            return {"result": res.relation("result")}
        finally:
            res.close()


if __name__ == "__main__":  # pragma: no cover
    for rel, rows in run().items():
        print(f"== {rel} ==")
        for row in rows:
            print(row)
