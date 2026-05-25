"""Port of wirelog `examples/05-crc32-checksum` to PyreWire.

Demonstrates wirelog's `crc32_ethernet()` built-in by validating frame
payload checksums. The upstream example loads `frames.csv`; this port
keeps the same rows inline so the script is self-contained.
"""

from __future__ import annotations

from pyrewire import BatchProgram
from pyrewire.batch import Result

FRAME_ROWS = [
    ("F001", "DEADBEEF0102030405060708", 3838819244),
    ("F002", "CAFEBABE0A0B0C0D0E0F1011", 250819451),
    ("F003", "AABBCCDD1213141516171819", 1661565857),
    ("F004", "001122334455667788990011", 9999999999),
    ("F005", "FFEEDDCCBBAA998877665544", 2259087609),
    ("F006", "0102030405060708090A0B0C", 1234567890),
]
_FRAME_BY_STORED = {stored: (frame_id, payload) for frame_id, payload, stored in FRAME_ROWS}

SRC = """
.decl frame(frame_id: symbol, payload: symbol, stored_crc32: int64)
frame("F001", "DEADBEEF0102030405060708", 3838819244).
frame("F002", "CAFEBABE0A0B0C0D0E0F1011", 250819451).
frame("F003", "AABBCCDD1213141516171819", 1661565857).
frame("F004", "001122334455667788990011", 9999999999).
frame("F005", "FFEEDDCCBBAA998877665544", 2259087609).
frame("F006", "0102030405060708090A0B0C", 1234567890).

.decl frame_crc(frame_id: symbol, payload: symbol, stored_crc32: int64, computed_crc32: int64)
frame_crc(Id, Payload, Stored, crc32_ethernet(Payload)) :-
    frame(Id, Payload, Stored).

.decl valid_frame(frame_id: symbol, payload: symbol, stored_crc32: int64)
valid_frame(Id, Payload, Stored) :-
    frame_crc(Id, Payload, Stored, Stored).

.decl corrupt_frame(frame_id: symbol, stored_crc32: int64, computed_crc32: int64)
corrupt_frame(Id, Stored, Computed) :-
    frame_crc(Id, _, Stored, Computed),
    Computed != Stored.
"""


def _relation_or_empty(res: Result, name: str) -> list[tuple]:
    if res.cardinality(name) == 0:
        return []
    return res.relation(name)


def _decode_frame_crc(rows: list[tuple]) -> list[tuple[str, str, int, int]]:
    decoded = []
    for _raw_id, _raw_payload, stored, computed in rows:
        frame_id, payload = _FRAME_BY_STORED[stored]
        decoded.append((frame_id, payload, stored, computed))
    return decoded


def _decode_valid_frame(rows: list[tuple]) -> list[tuple[str, str, int]]:
    decoded = []
    for _raw_id, _raw_payload, stored in rows:
        frame_id, payload = _FRAME_BY_STORED[stored]
        decoded.append((frame_id, payload, stored))
    return decoded


def _decode_corrupt_frame(rows: list[tuple]) -> list[tuple[str, int, int]]:
    decoded = []
    for _raw_id, stored, computed in rows:
        frame_id, _payload = _FRAME_BY_STORED[stored]
        decoded.append((frame_id, stored, computed))
    return decoded


def run() -> dict[str, list[tuple]]:
    """Return all computed checksums plus valid/corrupt partitions."""
    with BatchProgram.from_string(SRC) as bp:
        bp.optimize()
        res = bp.evaluate()
        try:
            return {
                "frame_crc": _decode_frame_crc(_relation_or_empty(res, "frame_crc")),
                "valid_frame": _decode_valid_frame(_relation_or_empty(res, "valid_frame")),
                "corrupt_frame": _decode_corrupt_frame(_relation_or_empty(res, "corrupt_frame")),
            }
        finally:
            res.close()


if __name__ == "__main__":  # pragma: no cover
    for rel, rows in run().items():
        print(f"== {rel} ==")
        for row in rows:
            print(row)
