# Quickstart

## Easy session: inline facts + interactive insert

```python
from pyrewire import EasySession

SRC = """
.decl friend(a: symbol, b: symbol)
.decl mutual(a: symbol, b: symbol)
mutual(A, B) :- friend(A, B), friend(B, A).
"""

# snapshot() reads a relation's full IDB contents.
with EasySession(SRC) as s:
    s.insert("friend", ["alice", "bob"])
    s.insert("friend", ["bob", "alice"])
    print(s.snapshot("mutual"))   # [('alice', 'bob'), ('bob', 'alice')]

# step() drives one fixpoint step and returns the incremental deltas as
# (relation, row, diff) tuples. A session commits to a single mode the
# first time it is queried, so step() and snapshot() each need a fresh
# session.
with EasySession(SRC) as s:
    s.insert("friend", ["alice", "bob"])
    s.insert("friend", ["bob", "alice"])
    for relation, row, diff in s.step():
        print(relation, row, diff)   # e.g. mutual ('alice', 'bob') 1
```

String values are auto-interned through a per-session intern table;
subsequent `intern()` calls for the same string return the cached id
without crossing the FFI boundary. See
[step vs snapshot](semantics/step-vs-snapshot.md) for the mode machine.

## Batch program: one-shot evaluation

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
        print(res.cardinality("reach"))      # 2
        print(res.relation("reach"))         # [(1,), (2,)]
    finally:
        res.close()
```

## Advanced session: NumPy zero-copy insert

```python
import numpy as np
from pyrewire import Program, Session, BackendKind

prog = Program.from_string(".decl edge(x: int32, y: int32)\n")
arr = np.arange(2000, dtype=np.int64).reshape(1000, 2)

with Session(prog, backend=BackendKind.COLUMNAR, num_workers=4) as s:
    s.insert_batch("edge", arr)   # zero Python-side copies
```

## Asyncio: drive a session from an event loop

```python
import asyncio
from pyrewire import AsyncBatchProgram

SRC = """
.decl edge(x: int32, y: int32)
.decl reach(x: int32)
edge(1, 2). edge(2, 3).
reach(X) :- edge(X, _).
"""

async def main() -> None:
    async with AsyncBatchProgram(src=SRC) as bp:
        await bp.optimize()
        res = await bp.evaluate()
        try:
            print(res.cardinality("reach"))   # 2
        finally:
            res.close()

asyncio.run(main())
```

Every async wrapper owns its own dedicated worker thread so multiple
sessions can run in parallel via `asyncio.gather`.

## Avoiding the z-set +2 trap

Re-inserting a row that is already present from an inline `.dl` fact
raises its multiplicity to `+2`; a single `remove()` will not retract
it. Use `preview_inline_facts(rel)` to detect this before it happens:

```python
from pyrewire import EasySession

src = """
.decl friend(a: symbol, b: symbol)
friend("alice", "bob").
"""
incoming = [["alice", "bob"], ["carol", "dave"]]

with EasySession(src) as s:
    already = {tuple(r) for r in s.preview_inline_facts("friend")}
    for row in incoming:
        if tuple(row) not in already:
            s.insert("friend", row)
```

Or use the shorthand:

```python
from pyrewire import EasySession

src = """
.decl friend(a: symbol, b: symbol)
friend("alice", "bob").
"""

with EasySession(src) as s:
    inserted = s.insert_with_dedupe("friend", ["alice", "bob"])
```
