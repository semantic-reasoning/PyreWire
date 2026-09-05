# SPDX-License-Identifier: Apache-2.0 OR GPL-3.0-or-later
"""Port of wirelog `examples/14-arithmetic-operations` to PyreWire.

Two programs. The first evaluates arithmetic expressions in a rule head
over `int64` columns. The second runs the `min` / `max` / `average` /
`count` aggregates, where `average` requires a declared `float` operand.

Requires wirelog >= 0.60.0. Both halves are parse errors on 0.54.0 and
older: arithmetic expressions in a rule head, multi-line `.decl`
continuations, `float` columns, float literals and `average()` all
arrived together. PyreWire needed no change to carry them — a `float`
column decodes as a Python `float` through the existing result path.

Float values reach a program through its source text only.
`EasySession.insert()` carries `int64` lanes and raises `ExecError` on a
Python `float`; wirelog's typed-ingress entry point
(`wirelog_session_insert_typed`) is not wrapped yet, which is why this
example uses `BatchProgram` with inline facts rather than a session.

Two behaviors are easy to misread and are demonstrated deliberately:

- Arithmetic parses left-associatively. `A + B * C` means `(A + B) * C`,
  not the conventional multiplication-first grouping, so the
  `precedence` row derives `22` rather than `14`. Use explicit
  intermediate relations when conventional grouping is needed.
- The typed float ingress canonicalizes `-0.0` and `+0.0` to the same
  `+0.0` value, so the two `zero_input` facts collapse to one row.

Division truncates toward zero (`-17 / 5` is `-3`) and the remainder
keeps the dividend's sign (`-17 % 5` is `-2`). The rule filters out rows
with `B == 0` rather than relying on a default for division by zero.
"""

from __future__ import annotations

import math

from pyrewire import BatchProgram, wirelog_version

ARITHMETIC_SRC = """
.decl sample(label: symbol, a: int64, b: int64, c: int64)
.decl result(label: symbol, added: int64, difference: int64,
             product: int64, quotient: int64, remainder: int64,
             precedence: int64)

sample("negative", -17, 5, 2).
sample("positive", 17, 5, 2).
sample("precedence", 8, 3, 2).

result(Label, A + B, A - B, A * B, A / B, A % B, A + B * C)
    :- sample(Label, A, B, C), B != 0.
"""

AGGREGATE_SRC = """
.decl sample(a: int64, value: float)
.decl zero_input(value: float)
.decl zero_observed(value: float)
.decl minimum(value: int64)
.decl maximum(value: int64)
.decl average_value(value: float)
.decl sample_count(value: int64)

sample(-17, 1.5).
sample(17, 2.5).
sample(8, 3.5).
zero_input(-0.0).
zero_input(0.0).

minimum(min(A)) :- sample(A, _).
maximum(max(A)) :- sample(A, _).
average_value(average(Value)) :- sample(_, Value).
sample_count(count(A)) :- sample(A, _).
zero_observed(Value) :- zero_input(Value).
"""

AGGREGATE_RELATIONS = (
    "minimum",
    "maximum",
    "average_value",
    "sample_count",
    "zero_observed",
)

# `symbol` columns come back as interned ids, not the source spelling, so
# the example resolves the label itself. `added` (`A + B`) is unique per
# row, which makes it a stable key. Example 05 decodes symbols the same
# way.
_LABEL_BY_ADDED = {-12: "negative", 22: "positive", 11: "precedence"}

MINIMUM_WIRELOG = (0, 60, 0)


def wirelog_supports_float() -> bool:
    """Whether the loaded engine is new enough to run this example."""
    parts = tuple(int(part) for part in wirelog_version().split(".")[:3])
    return parts >= MINIMUM_WIRELOG


def _run_arithmetic() -> list[tuple]:
    with BatchProgram.from_string(ARITHMETIC_SRC) as bp:
        bp.optimize()
        res = bp.evaluate()
        try:
            return sorted((_LABEL_BY_ADDED[row[1]], *row[1:]) for row in res.relation("result"))
        finally:
            res.close()


def _run_aggregates() -> dict[str, list[tuple]]:
    with BatchProgram.from_string(AGGREGATE_SRC) as bp:
        bp.optimize()
        res = bp.evaluate()
        try:
            return {name: res.relation(name) for name in AGGREGATE_RELATIONS}
        finally:
            res.close()


def run() -> dict[str, list[tuple]]:
    out: dict[str, list[tuple]] = {"result": _run_arithmetic()}
    out.update(_run_aggregates())
    return out


if __name__ == "__main__":  # pragma: no cover
    if not wirelog_supports_float():
        raise SystemExit(
            f"wirelog {wirelog_version()} is too old for this example; "
            f"{'.'.join(str(p) for p in MINIMUM_WIRELOG)} or newer is required"
        )

    results = run()
    for relation, rows in results.items():
        print(f"== {relation} ==")
        for row in rows:
            print(row)

    (zero,) = results["zero_observed"][0]
    sign = "+" if math.copysign(1.0, zero) > 0 else "-"
    print(f"\n-0.0 and +0.0 both ingressed as {sign}0.0")
