"""Asyncio-friendly proxies around the synchronous wirelog session APIs (#29).

wirelog sessions are not thread-safe; running every call from one
dedicated worker thread satisfies wirelog's "no concurrent calls on
the same session" invariant while letting an asyncio event loop
`await` session operations.

Each async wrapper owns a `ThreadPoolExecutor(max_workers=1)`. The
underlying synchronous session is constructed on that executor's
thread so every `LIB.*` call wirelog sees comes from the same OS
thread — no explicit lock is needed beyond what the single-worker
pool already enforces.

Multiple async sessions can run in parallel because each carries its
own dedicated thread.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
from collections.abc import Sequence
from pathlib import Path
from types import TracebackType
from typing import Any

from .batch import BatchProgram, Result
from .program import Program
from .session import EasySession, Session

# `EasySession.step` / `snapshot` (#10/#11) and the related delta-mode
# helpers are not yet on the synchronous class — they ship with
# upstream wirelog#852. AsyncEasySession exposes only the methods that
# exist today; the missing ones will be mirrored when #10/#11 land.


class _AsyncProxyBase:
    """Run every call on a dedicated single-worker executor."""

    __slots__ = ("_pool", "_closed")

    def __init__(self) -> None:
        self._pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="pyrewire-async"
        )
        self._closed: bool = False

    async def _call(self, fn: Any, /, *args: Any, **kw: Any) -> Any:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._pool, lambda: fn(*args, **kw))

    async def aclose(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._pool.shutdown(wait=True)


class AsyncEasySession(_AsyncProxyBase):
    """Async proxy around `EasySession`. Use as `async with`.

    Currently exposes `intern` / `insert` / `remove` / `insert_sym` /
    `remove_sym` / `preview_inline_facts` / `insert_with_dedupe`.
    `step` / `snapshot` will be added in lockstep with the synchronous
    `EasySession` methods (#10 / #11).
    """

    def __init__(self, dl_src: str, **kw: Any) -> None:
        super().__init__()
        self._dl_src = dl_src
        self._init_kw = kw
        self._inner: EasySession | None = None

    async def __aenter__(self) -> AsyncEasySession:
        self._inner = await self._call(EasySession, self._dl_src, **self._init_kw)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._inner is not None:
            await self._call(self._inner.close)
        await self.aclose()

    def _need_inner(self) -> EasySession:
        if self._inner is None:
            raise RuntimeError("AsyncEasySession used outside `async with`; call __aenter__")
        return self._inner

    async def intern(self, value: str) -> int:
        return int(await self._call(self._need_inner().intern, value))

    async def insert(self, relation: str, row: Sequence[Any]) -> None:
        await self._call(self._need_inner().insert, relation, row)

    async def remove(self, relation: str, row: Sequence[Any]) -> None:
        await self._call(self._need_inner().remove, relation, row)

    async def insert_sym(self, relation: str, *symbols: str) -> None:
        await self._call(self._need_inner().insert_sym, relation, *symbols)

    async def remove_sym(self, relation: str, *symbols: str) -> None:
        await self._call(self._need_inner().remove_sym, relation, *symbols)

    async def preview_inline_facts(self, relation: str) -> list[tuple[Any, ...]]:
        rows = await self._call(self._need_inner().preview_inline_facts, relation)
        return list(rows)

    async def insert_with_dedupe(self, relation: str, row: Sequence[Any]) -> bool:
        return bool(await self._call(self._need_inner().insert_with_dedupe, relation, row))


class AsyncSession(_AsyncProxyBase):
    """Async proxy around the advanced `Session`. Pass an already-parsed
    `Program`; the borrow guarantee applies just as in the sync class."""

    def __init__(self, program: Program, **session_kw: Any) -> None:
        super().__init__()
        self._program = program
        self._session_kw = session_kw
        self._inner: Session | None = None

    async def __aenter__(self) -> AsyncSession:
        self._inner = await self._call(Session, self._program, **self._session_kw)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._inner is not None:
            await self._call(self._inner.close)
        await self.aclose()

    def _need_inner(self) -> Session:
        if self._inner is None:
            raise RuntimeError("AsyncSession used outside `async with`; call __aenter__")
        return self._inner

    async def insert(self, relation: str, rows: Sequence[Sequence[int]]) -> None:
        await self._call(self._need_inner().insert, relation, rows)

    async def remove(self, relation: str, rows: Sequence[Sequence[int]]) -> None:
        await self._call(self._need_inner().remove, relation, rows)

    async def insert_batch(self, relation: str, rows: Any) -> None:
        await self._call(self._need_inner().insert_batch, relation, rows)

    async def remove_batch(self, relation: str, rows: Any) -> None:
        await self._call(self._need_inner().remove_batch, relation, rows)

    async def step(self) -> list[tuple[str, tuple[int, ...], int]]:
        rows = await self._call(self._need_inner().step)
        return list(rows)

    async def snapshot(self) -> list[tuple[str, tuple[int, ...]]]:
        rows = await self._call(self._need_inner().snapshot)
        return list(rows)

    async def preview_inline_facts(self, relation: str) -> list[tuple[Any, ...]]:
        rows = await self._call(self._need_inner().preview_inline_facts, relation)
        return list(rows)


class AsyncBatchProgram(_AsyncProxyBase):
    """Async proxy around `BatchProgram`."""

    def __init__(self, src: str | None = None, *, file: str | Path | None = None) -> None:
        super().__init__()
        if (src is None) == (file is None):
            raise ValueError("AsyncBatchProgram: pass exactly one of src=/file=")
        self._src = src
        self._file = file
        self._inner: BatchProgram | None = None

    async def __aenter__(self) -> AsyncBatchProgram:
        if self._src is not None:
            self._inner = await self._call(BatchProgram.from_string, self._src)
        else:
            assert self._file is not None
            self._inner = await self._call(BatchProgram.from_file, self._file)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._inner is not None:
            await self._call(self._inner.close)
        await self.aclose()

    def _need_inner(self) -> BatchProgram:
        if self._inner is None:
            raise RuntimeError("AsyncBatchProgram used outside `async with`; call __aenter__")
        return self._inner

    async def optimize(self) -> None:
        await self._call(self._need_inner().optimize)

    async def load_all_facts(self) -> None:
        await self._call(self._need_inner().load_all_facts)

    async def load_input_files(self) -> None:
        await self._call(self._need_inner().load_input_files)

    async def evaluate(self) -> Result:
        return await self._call(self._need_inner().evaluate)  # type: ignore[no-any-return]


__all__ = ["AsyncEasySession", "AsyncSession", "AsyncBatchProgram"]
