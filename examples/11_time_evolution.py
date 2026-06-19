# SPDX-License-Identifier: Apache-2.0 OR GPL-3.0-or-later
"""Port of wirelog `examples/11-time-evolution` to PyreWire.

Each `EasySession.step()` is a discrete time epoch — the delta
callback fires only for the rows newly derived in that step, not the
full snapshot. Three epochs are driven here:

1. Insert e1(error), e2(info), e3(error) — `alert` fires for e1 and e3.
2. Insert e4(info) — no new alerts.
3. Insert e5(error) — `alert` fires for e5.

Requires a libwirelog that includes wirelog#852 (tagged `> v0.41.0` —
tracked in wirelog#859); older builds may emit empty delta lists.
"""

from __future__ import annotations

from pyrewire import EasySession

SRC = """
.decl event(id: symbol, kind: symbol)
.decl alert(id: symbol)
alert(ID) :- event(ID, "error").
"""


def run() -> dict[str, list[tuple]]:
    """Drive three epochs and return the deltas each emits."""
    epochs: dict[str, list[tuple]] = {}
    with EasySession(SRC) as s:
        s.insert_sym("event", "e1", "error")
        s.insert_sym("event", "e2", "info")
        s.insert_sym("event", "e3", "error")
        epochs["epoch1_errors_emerge"] = s.step()

        s.insert_sym("event", "e4", "info")
        epochs["epoch2_only_info"] = s.step()

        s.insert_sym("event", "e5", "error")
        epochs["epoch3_one_more_alert"] = s.step()
    return epochs


if __name__ == "__main__":  # pragma: no cover
    for label, deltas in run().items():
        print(f"== {label} ==")
        for rel, row, diff in deltas:
            sign = "+" if diff > 0 else "-"
            print(f"{sign}{rel}{row}")
