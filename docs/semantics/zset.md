# Z-set multiplicity

Every row in a wirelog relation carries an **integer multiplicity**.

- [`insert`][pyrewire.session.EasySession.insert] raises the row's
  multiplicity by `+1`.
- [`remove`][pyrewire.session.EasySession.remove] lowers it by `-1`.
- A row is observable while its multiplicity is `> 0`.

This is the *z-set* semantics that lets wirelog support efficient
incremental updates: a `remove` is symmetric with `insert`, and an
unchanged row's multiplicity is preserved across recomputation.

## The inline-fact trap

!!! warning
    A program that **declares an inline fact** and a host that
    **inserts the same row** produces multiplicity `+2`. A single
    `remove()` leaves the row with multiplicity `+1` — still
    observable.

```python
# expected: row stays in `friend` even after one remove

from pyrewire import EasySession

SRC = """
.decl friend(a: symbol, b: symbol)
friend("alice", "bob").
"""

with EasySession(SRC) as s:
    s.insert("friend", ["alice", "bob"])    # multiplicity now +2
    s.remove("friend", ["alice", "bob"])    # multiplicity now +1
    # `friend("alice", "bob")` is still derived.
```

## Recommended pattern

Define EDB rows **either** in the source **or** via host calls — not
both. When both must coexist, dedupe at the host boundary:

```python
from pyrewire import EasySession

SRC = """
.decl friend(a: symbol, b: symbol)
friend("alice", "bob").
"""

incoming = [("alice", "bob"), ("alice", "carol")]

with EasySession(SRC) as s:
    already = {tuple(r) for r in s.preview_inline_facts("friend")}
    for row in incoming:
        if tuple(row) not in already:
            s.insert("friend", row)
    # "alice", "bob" multiplicity stays at +1.
```

The shorthand
[`insert_with_dedupe`][pyrewire.session.EasySession.insert_with_dedupe]
collapses the membership test:

```python
from pyrewire import EasySession

SRC = """
.decl friend(a: symbol, b: symbol)
friend("alice", "bob").
"""

with EasySession(SRC) as s:
    inserted_new = s.insert_with_dedupe("friend", ("alice", "bob"))
    # `inserted_new` is False — the row was already present.
```

## Why wirelog does not deduplicate automatically

wirelog must preserve multiplicities across iterative evaluation —
the same row may legitimately enter with `+1` from two different
rules, and aggregations care about the count. The choice is
**correctness over ergonomics**: the engine never decides what the
caller meant; PyreWire's deduplication helpers make the safe pattern
the obvious one.
