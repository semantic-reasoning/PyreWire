# Step vs snapshot

PyreWire sessions evaluate datalog programs in one of two **mutually
exclusive** modes:

- **Incremental** — drive `step()` after each batch of inserts /
  removes; receive deltas through `set_delta_callback` or the return
  of `step()`. Suited to streaming workloads where you want to see
  *what changed*.
- **Query** — call `snapshot()` once after all data is loaded;
  receive every IDB tuple. Suited to one-shot queries where you want
  *what is*.

## Why mixing breaks correctness

Both paths derive IDB rows. If you call `step()` and then `snapshot()`
on the same session, the snapshot may re-emit tuples the step phase
already delivered, producing apparent duplicates that the engine
*itself* never created.

!!! warning
    The mode boundary is enforced **once per session lifetime**:
    after the first `step()` (or
    [`set_delta_callback`][pyrewire.session.Session.set_delta_callback])
    the session is in INCREMENTAL mode forever; after the first
    `snapshot()` it is in QUERY mode forever.

## What PyreWire enforces

Crossing modes raises
[`WirelogModeError`][pyrewire._core.errors.WirelogModeError]:

```python
# expected: WirelogModeError on the second call

from pyrewire import Program, Session
from pyrewire._core.errors import WirelogModeError

prog = Program.from_string(".decl edge(x: int32, y: int32)\n")

with Session(prog) as s:
    s.insert("edge", [(1, 2)])    # commits INCREMENTAL
    try:
        s.snapshot()              # raises WirelogModeError
    except WirelogModeError as e:
        print(f"refused as expected: {e}")
```

The reverse — calling `step()` after `snapshot()` — is rejected the
same way.

## Correct patterns

### Two separate sessions

```python
from pyrewire import Program, Session

prog = Program.from_string(
    ".decl edge(x: int32, y: int32)\n"
    "edge(1, 2). edge(2, 3).\n"
)

# Phase 1: incremental updates
with Session(prog) as live:
    live.insert("edge", [(3, 4)])
    # …drive step() in a loop…

# Phase 2: snapshot the IDB
with Session(prog) as snap:
    rows = snap.snapshot()
```

### Use BatchProgram when you only need the closure

[`BatchProgram`][pyrewire.batch.BatchProgram] sidesteps the mode
machine entirely:

```python
from pyrewire import BatchProgram

src = """
.decl edge(x: int32, y: int32)
.decl reach(x: int32)
edge(1, 2). edge(2, 3).
reach(X) :- edge(X, _).
"""

with BatchProgram.from_string(src) as bp:
    bp.optimize()
    res = bp.evaluate()
    try:
        rows = res.relation("reach")
    finally:
        res.close()
```

The batch pipeline does one optimize → evaluate → CSV round-trip and
never enters either mode.
