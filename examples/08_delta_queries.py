"""Port of wirelog `examples/08-delta-queries` to PyreWire.

Demonstrates wirelog's delta-callback pipeline through `EasySession.step`.
Five `can(user, permission)` facts are inserted and a single step()
runs the access-control rule (`granted(U, P) :- can(U, P)`); the
returned delta list mirrors what the C demo prints from its
`wirelog_easy_set_delta_cb` callback.

Requires a libwirelog that includes wirelog#852 (tagged `> v0.41.0` —
tracked in wirelog#859); older builds will return an empty delta list.
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


def run() -> dict[str, list[tuple]]:
    """Insert every grant in one batch and return the delta list step() emits."""
    with EasySession(SRC) as s:
        for user, perm in GRANTS:
            s.insert_sym("can", user, perm)
        return {"step_deltas": s.step()}


if __name__ == "__main__":  # pragma: no cover
    out = run()
    for rel, row, diff in out["step_deltas"]:
        sign = "+" if diff > 0 else "-"
        print(f"{sign}{rel}{row}")
