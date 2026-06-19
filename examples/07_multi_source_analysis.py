# SPDX-License-Identifier: Apache-2.0 OR GPL-3.0-or-later
"""Port of wirelog `examples/07-multi-source-analysis` to PyreWire.

Two CRM sources (`src_a`, `src_b`) supply customer records. The
program produces four derived relations:

- `integrated`: unified customer table, source A wins on conflict.
- `a_only` / `b_only`: customers seen in only one source.
- `conflict`: customers where A and B disagree on name or country.

The upstream example reads the two sources from CSV files; this port
inlines the same records as `src_a` / `src_b` facts. The
`customers_per_country` aggregate from the upstream example is also
included to exercise `count(...)` against the integrated table.
"""

from __future__ import annotations

from pyrewire import BatchProgram

SRC = """
.decl src_a(id: symbol, name: symbol, country: symbol)
src_a("C001", "Alice Martin",   "US").
src_a("C002", "Bob Chen",       "CN").
src_a("C003", "Carol Smith",    "UK").
src_a("C004", "David Kim",      "KR").
src_a("C005", "Eve Tanaka",     "JP").
src_a("C006", "Frank Muller",   "DE").
src_a("C007", "Grace Lee",      "KR").

.decl src_b(id: symbol, name: symbol, country: symbol)
src_b("C002", "Bob Chen",       "CN").
src_b("C003", "Caroline Smith", "GB").
src_b("C004", "David Kim",      "KR").
src_b("C008", "Henry Dubois",   "FR").
src_b("C009", "Iris Rossi",     "IT").
src_b("C010", "James Park",     "KR").

.decl integrated(id: symbol, name: symbol, country: symbol)
integrated(Id, Name, Country) :- src_a(Id, Name, Country).
integrated(Id, Name, Country) :-
    src_b(Id, Name, Country),
    !src_a(Id, _, _).

.decl in_a(id: symbol)
in_a(Id) :- src_a(Id, _, _).

.decl in_b(id: symbol)
in_b(Id) :- src_b(Id, _, _).

.decl a_only(id: symbol)
a_only(Id) :- in_a(Id), !in_b(Id).

.decl b_only(id: symbol)
b_only(Id) :- in_b(Id), !in_a(Id).

.decl conflict(id: symbol)
conflict(Id) :-
    src_a(Id, NameA, _),
    src_b(Id, NameB, _),
    NameA != NameB.
conflict(Id) :-
    src_a(Id, _, CountryA),
    src_b(Id, _, CountryB),
    CountryA != CountryB.

.decl customers_per_country(country: symbol, n: int64)
customers_per_country(Country, count(Id)) :- integrated(Id, _, Country).
"""


def run() -> dict[str, list[tuple]]:
    """Return every derived relation the upstream example computes."""
    with BatchProgram.from_string(SRC) as bp:
        bp.optimize()
        res = bp.evaluate()
        try:
            return {
                "integrated": res.relation("integrated"),
                "a_only": res.relation("a_only"),
                "b_only": res.relation("b_only"),
                "conflict": res.relation("conflict"),
                "customers_per_country": res.relation("customers_per_country"),
            }
        finally:
            res.close()


if __name__ == "__main__":  # pragma: no cover
    for rel, rows in run().items():
        print(f"== {rel} ==")
        for row in rows:
            print(row)
