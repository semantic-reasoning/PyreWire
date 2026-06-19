# SPDX-License-Identifier: Apache-2.0 OR GPL-3.0-or-later
"""Port of wirelog `examples/04-hash-functions` to PyreWire.

Demonstrates wirelog's built-in `hash()` functor for the three tasks
the upstream example covers:

1. **Email fingerprint** — `hash(email)` collapses duplicate addresses
   to a single integer key.
2. **Deduplication** — records sharing a fingerprint are the same
   person; keep the one with the smallest `id`.
3. **Checksum validation** — `hash(id)` is stored at ingest time; a
   mismatch signals that the row was corrupted after ingest.
"""

from __future__ import annotations

import contextlib
import os
import tempfile

from pyrewire import BatchProgram
from pyrewire.batch import Result

CHECKSUM_ROWS = [
    (1, 3439722301264460078),
    (2, 2343778756980564547),
    (3, 5589565451239960189),
    (4, -3881494802266689160),
    (5, 1234567890123456789),
    (6, 7753311634367670075),
]

_NAME_BY_ID = {
    1: "alice",
    2: "bob",
    3: "carol",
    4: "alice_dup",
    5: "dave",
    6: "bob_dup",
}

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

.decl checksum(id: int64, stored: int64)

.decl valid_record(id: int64, name: symbol)
valid_record(Id, Name) :-
    checksum(Id, Stored),
    record(Id, Name, _),
    hash(Id) = Stored.

.decl corrupted_record(id: int64, name: symbol, stored: int64, computed: int64)
corrupted_record(Id, Name, Stored, hash(Id)) :-
    checksum(Id, Stored),
    record(Id, Name, _),
    hash(Id) != Stored.
"""


def _write_checksum_csv() -> str:
    fd, path = tempfile.mkstemp(prefix="pyrewire_hash_checksums_", suffix=".csv")
    with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
        for record_id, stored in CHECKSUM_ROWS:
            fh.write(f"{record_id},{stored}\n")
    return path


def _relation_or_empty(res: Result, name: str) -> list[tuple]:
    if res.cardinality(name) == 0:
        return []
    return res.relation(name)


def _decode_valid_record(rows: list[tuple]) -> list[tuple[int, str]]:
    return [(record_id, _NAME_BY_ID[record_id]) for record_id, _raw_name in rows]


def _decode_corrupted_record(rows: list[tuple]) -> list[tuple[int, str, int, int]]:
    return [
        (record_id, _NAME_BY_ID[record_id], stored, computed)
        for record_id, _raw_name, stored, computed in rows
    ]


def run() -> dict[str, list[tuple]]:
    """Return fingerprint, deduplication, and checksum-validation outputs."""
    checksum_path = _write_checksum_csv()
    with BatchProgram.from_string(SRC) as bp:
        try:
            bp.optimize()
            bp.load_facts_from_csv("checksum", checksum_path)
            res = bp.evaluate()
            try:
                return {
                    "email_fp": res.relation("email_fp"),
                    "unique_record": res.relation("unique_record"),
                    "valid_record": _decode_valid_record(_relation_or_empty(res, "valid_record")),
                    "corrupted_record": _decode_corrupted_record(
                        _relation_or_empty(res, "corrupted_record")
                    ),
                }
            finally:
                res.close()
        finally:
            with contextlib.suppress(OSError):
                os.unlink(checksum_path)


if __name__ == "__main__":  # pragma: no cover
    for rel, rows in run().items():
        print(f"== {rel} ==")
        for row in rows:
            print(row)
