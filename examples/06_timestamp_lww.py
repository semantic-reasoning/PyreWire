"""Port of wirelog `examples/06-timestamp-lww` to PyreWire.

Last-Writer-Wins via the `max()` aggregate: for each key, keep the
row carrying the latest timestamp.
"""

from __future__ import annotations

from pyrewire import BatchProgram

SRC = """
.decl update(id: int32, ts: int64, value: int32)
.decl latest_ts(id: int32, ts: int64)
.decl latest(id: int32, ts: int64, value: int32)

update(1, 1000, 100).
update(1, 2000, 200).
update(1, 1500, 150).
update(2, 500, 30).
update(2, 800, 40).

latest_ts(Id, max(Ts)) :- update(Id, Ts, _).
latest(Id, Ts, V) :- latest_ts(Id, Ts), update(Id, Ts, V).
"""


def run() -> dict[str, list[tuple]]:
    with BatchProgram.from_string(SRC) as bp:
        bp.optimize()
        res = bp.evaluate()
        try:
            return {
                "latest_ts": res.relation("latest_ts"),
                "latest": res.relation("latest"),
            }
        finally:
            res.close()


if __name__ == "__main__":  # pragma: no cover
    for rel, rows in run().items():
        print(f"== {rel} ==")
        for row in rows:
            print(row)
