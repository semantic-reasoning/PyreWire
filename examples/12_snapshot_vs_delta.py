"""Port of wirelog `examples/12-snapshot-vs-delta` to PyreWire.

Compares the two read paths exposed by `EasySession`:

- **delta mode** (`step()`) — receives the per-step delta list.
- **snapshot mode** (`snapshot()`) — materialises the full relation
  contents at the current point in time.

Both paths are driven over identical inputs in two independent
sessions and should produce the same set of `granted` rows.

Note: PyreWire ships its own `examples/12_batch_vs_session.py` which
contrasts the batch executor with a session preview — a different
comparison. This file (`12_snapshot_vs_delta.py`) is the port of
wirelog's example 12, which contrasts `step()` and `snapshot()`.

Requires a libwirelog that includes wirelog#852 (tagged `> v0.41.0` —
tracked in wirelog#859); older builds may return an empty delta list.
"""

from __future__ import annotations

from pyrewire import EasySession

SRC = """
.decl can(user: symbol, perm: symbol)
.decl granted(user: symbol, perm: symbol)
granted(U, P) :- can(U, P).
"""

GRANTS = [
    ("alice", "read"),
    ("alice", "write"),
    ("bob", "read"),
    ("bob", "admin"),
    ("carol", "read"),
]


def _insert_grants_neutral(s: EasySession) -> None:
    """Insert via the mode-neutral `insert()` so the session can still
    be driven into either QUERY (snapshot) or INCREMENTAL (step) mode."""
    for user, perm in GRANTS:
        s.insert("can", [user, perm])


def run() -> dict[str, list[tuple]]:
    """Drive both paths and return the delta + snapshot row lists."""
    with EasySession(SRC) as sd:
        _insert_grants_neutral(sd)
        delta_rows = [(rel, row) for rel, row, diff in sd.step() if diff > 0 and rel == "granted"]

    with EasySession(SRC) as ss:
        _insert_grants_neutral(ss)
        snapshot_rows = [("granted", row) for row in ss.snapshot("granted")]

    return {"delta_rows": delta_rows, "snapshot_rows": snapshot_rows}


if __name__ == "__main__":  # pragma: no cover
    out = run()
    delta_set = set(out["delta_rows"])
    snap_set = set(out["snapshot_rows"])
    print("=== delta mode ===")
    for entry in sorted(out["delta_rows"]):
        print(entry)
    print("=== snapshot mode ===")
    for entry in sorted(out["snapshot_rows"]):
        print(entry)
    print("PASS" if delta_set == snap_set else "MISMATCH")
