"""Port of wirelog `examples/04-hash-functions` to PyreWire.

Demonstrates wirelog's built-in `hash()` functor for two of the three
tasks the upstream example covers:

1. **Email fingerprint** — `hash(email)` collapses duplicate addresses
   to a single integer key.
2. **Deduplication** — records sharing a fingerprint are the same
   person; keep the one with the smallest `id`.

The upstream example's third task (checksum validation against a
literally-stored `hash(id)` value) is intentionally omitted from this
port: validating against a *literal* stored checksum requires the
host program to precompute wirelog's `hash()` output, which the
inline-facts style does not express cleanly. The dedup half stays
self-contained.
"""

from __future__ import annotations

from pyrewire import BatchProgram

SRC = """
.decl record(id: int64, name: symbol, email: symbol)
record(1, "alice", "alice@example.com").
record(2, "bob", "bob@example.com").
record(3, "carol", "carol@example.com").
record(4, "alice_dup", "alice@example.com").
record(5, "dave", "dave@example.com").
record(6, "bob_dup", "bob@example.com").

.decl email_fp(id: int64, name: symbol, email: symbol, fp: int64)
email_fp(Id, Name, Email, hash(Email)) :- record(Id, Name, Email).

.decl superseded(id: int64)
superseded(Id) :-
    email_fp(Id, _, _, Fp),
    email_fp(Other, _, _, Fp),
    Other < Id.

.decl unique_record(id: int64, name: symbol, email: symbol)
unique_record(Id, Name, Email) :-
    record(Id, Name, Email),
    !superseded(Id).
"""


def run() -> dict[str, list[tuple]]:
    """Return the fingerprint table and the deduplicated record set."""
    with BatchProgram.from_string(SRC) as bp:
        bp.optimize()
        res = bp.evaluate()
        try:
            return {
                "email_fp": res.relation("email_fp"),
                "unique_record": res.relation("unique_record"),
            }
        finally:
            res.close()


if __name__ == "__main__":  # pragma: no cover
    for rel, rows in run().items():
        print(f"== {rel} ==")
        for row in rows:
            print(row)
