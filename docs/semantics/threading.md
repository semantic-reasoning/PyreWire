# Threading

!!! warning
    **wirelog sessions are not thread-safe.** Concurrent calls into
    the same `wirelog_easy_session_t` / `wirelog_session_t` race on
    internal mutable state — even pairs of read-only helpers. This is
    the *single-caller invariant*.

PyreWire's job is to make this invariant easy to honour from Python,
where threading is the default for many libraries.

## What PyreWire does for you

Every session class takes an internal `threading.RLock`. Concurrent
`insert` / `remove` / `intern` / `step` / `snapshot` calls from
multiple Python threads are **serialised** for you — calls queue at
the lock, run one at a time, and never overlap inside wirelog.

```python
import threading
from pyrewire import EasySession

with EasySession(".decl name(s: symbol)\n") as s:
    def worker(name: str) -> None:
        s.insert_sym("name", name)

    threads = [
        threading.Thread(target=worker, args=(f"user_{i}",))
        for i in range(8)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    # All 8 names interned exactly once each; no race.
```

## Opting out

If you already manage your own mutual exclusion — or your workload
is single-threaded and you want one less acquire / release per call
— pass `lock=False`:

```python
from pyrewire import EasySession

with EasySession(".decl name(s: symbol)\n", lock=False) as s:
    # YOU are responsible for ensuring no two threads touch `s`
    # concurrently. Misuse here can segfault the process.
    s.insert_sym("name", "alice")
```

`Session(..., lock=False)` has the same opt-out.

## Asyncio

[`AsyncEasySession`][pyrewire.asyncio_session.AsyncEasySession],
[`AsyncSession`][pyrewire.asyncio_session.AsyncSession], and
[`AsyncBatchProgram`][pyrewire.asyncio_session.AsyncBatchProgram] give
each instance its own dedicated **single-worker thread pool**. All
FFI calls for one async session originate from the same OS thread,
satisfying the single-caller invariant by construction:

```python
import asyncio
from pyrewire import AsyncEasySession

async def main() -> None:
    async with AsyncEasySession(".decl x(a: int32)\n") as s:
        # Multiple concurrent awaits queue on the per-session thread
        # — never overlap inside wirelog.
        await asyncio.gather(*[s.insert("x", [i]) for i in range(100)])

asyncio.run(main())
```

Multiple async sessions can still run in parallel because each
carries its own dedicated thread:

```python
import asyncio
from pyrewire import AsyncEasySession

async def one() -> None:
    async with AsyncEasySession(".decl x(a: int32)\n") as s:
        await s.insert("x", [1])

async def main() -> None:
    # Independent sessions, independent threads, independent locks.
    await asyncio.gather(one(), one(), one())

asyncio.run(main())
```
