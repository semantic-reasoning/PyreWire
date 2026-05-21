# Compounds

A *compound* is a handle-backed side-relation entry. Wirelog assigns
each call to [`Session.make_compound`][pyrewire.session.Session.make_compound]
a fresh `uint64_t` handle that you can later reference by id.

## Session-local scope

!!! warning
    Compound handles are valid **only while the owning session is
    open**. Using a compound after its session has been closed is
    undefined behaviour on the C side; PyreWire's
    [`Compound`][pyrewire.compound.Compound] wrapper raises
    `ValueError` instead.

```python
# expected: ValueError after session close

from pyrewire import (
    BackendKind,
    ColumnType,
    CompoundArg,
    Program,
    Session,
)

prog = Program.from_string(".decl pair(x: int32, y: int32)\n")

s = Session(prog)
c = s.make_compound("pair", [
    CompoundArg(ColumnType.INT32, 1),
    CompoundArg(ColumnType.INT32, 2),
])
assert c.handle != 0
s.close()
try:
    _ = c.handle              # raises ValueError
except ValueError as e:
    print(f"refused as expected: {e}")
```

## Error codes

Two wirelog errors are worth surfacing explicitly:

- [`CompoundBusyError`][pyrewire._core.errors.CompoundBusyError] —
  **transient.** Another worker holds the arena epoch; retry with
  backoff and the call usually succeeds.
- [`CompoundSaturatedError`][pyrewire._core.errors.CompoundSaturatedError]
  — **escalated.** The compound arena's epoch is exhausted; the
  session must be reopened or the compound throughput reduced.

### Retry loop for CompoundBusyError

```python
import time
from pyrewire import (
    ColumnType,
    CompoundArg,
    Program,
    Session,
)
from pyrewire._core.errors import CompoundBusyError, CompoundSaturatedError

def make_compound_with_retry(s, functor, args, *, max_tries=5):
    delay = 0.001
    for _ in range(max_tries):
        try:
            return s.make_compound(functor, args)
        except CompoundBusyError:
            time.sleep(delay)
            delay *= 2
    raise

prog = Program.from_string(".decl pair(x: int32, y: int32)\n")
with Session(prog) as s:
    c = make_compound_with_retry(s, "pair", [
        CompoundArg(ColumnType.INT32, 1),
        CompoundArg(ColumnType.INT32, 2),
    ])
```

`CompoundSaturatedError` is **not** retryable — it signals that the
session has consumed every available epoch slot. Restart the session
or reduce the rate at which compounds are created.

## String columns

For `STRING`-typed compound arguments, pass the **intern id** of the
string, not the string itself. With `EasySession`, intern through
`s.intern("alice")`; with `Session`, call `s.seed_intern("alice", id)`
for known pairs (the advanced API has no public forward-intern entry
point).
