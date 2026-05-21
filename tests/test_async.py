"""Tests for `pyrewire.asyncio_session` (#29)."""

from __future__ import annotations

import asyncio

import pytest

from pyrewire.asyncio_session import (
    AsyncBatchProgram,
    AsyncEasySession,
    AsyncSession,
)
from pyrewire.program import Program

# ----------------------------------------------------------------------
# AsyncEasySession
# ----------------------------------------------------------------------


def test_async_easy_lifecycle():
    async def run() -> None:
        async with AsyncEasySession(".decl x(a: int32)\n") as s:
            await s.insert("x", [1])
            await s.insert("x", [2])

    asyncio.run(run())


def test_async_easy_intern_returns_id():
    async def run() -> None:
        async with AsyncEasySession(".decl name(s: symbol)\n") as s:
            i = await s.intern("alice")
            assert isinstance(i, int)

    asyncio.run(run())


def test_async_easy_insert_sym():
    async def run() -> None:
        async with AsyncEasySession(".decl name(s: symbol)\n") as s:
            await s.insert_sym("name", "alice")

    asyncio.run(run())


def test_async_easy_preview_and_dedupe():
    async def run() -> None:
        src = ".decl edge(x: int32, y: int32)\nedge(1, 2).\n"
        async with AsyncEasySession(src) as s:
            rows = await s.preview_inline_facts("edge")
            assert (1, 2) in rows
            assert (await s.insert_with_dedupe("edge", [1, 2])) is False
            assert (await s.insert_with_dedupe("edge", [3, 4])) is True

    asyncio.run(run())


def test_async_session_preview_inline_facts():
    async def run() -> None:
        prog = Program.from_string(".decl edge(x: int32, y: int32)\nedge(1, 2).\n")
        async with AsyncSession(prog) as s:
            rows = await s.preview_inline_facts("edge")
            assert (1, 2) in rows

    asyncio.run(run())


def test_async_easy_use_outside_with_raises():
    """Calling proxy methods before __aenter__ surfaces a runtime error."""

    async def run() -> None:
        s = AsyncEasySession(".decl x(a: int32)\n")
        with pytest.raises(RuntimeError):
            await s.intern("alice")
        await s.aclose()

    asyncio.run(run())


# ----------------------------------------------------------------------
# AsyncSession
# ----------------------------------------------------------------------


def test_async_session_lifecycle():
    async def run() -> None:
        prog = Program.from_string(".decl edge(x: int32, y: int32)\n")
        async with AsyncSession(prog) as s:
            await s.insert("edge", [(1, 2), (3, 4)])

    asyncio.run(run())


# ----------------------------------------------------------------------
# AsyncBatchProgram
# ----------------------------------------------------------------------


def test_async_batch_evaluate():
    async def run() -> None:
        src = (
            ".decl edge(x: int32, y: int32)\n"
            ".decl reach(x: int32)\n"
            "edge(1, 2).\n"
            "reach(X) :- edge(X, _).\n"
        )
        async with AsyncBatchProgram(src=src) as bp:
            await bp.optimize()
            res = await bp.evaluate()
            try:
                # Just verify the handle is non-null via cardinality call.
                assert res.cardinality("reach") >= 0
            finally:
                res.close()

    asyncio.run(run())


def test_async_batch_xor_constructor_arg():
    async def run() -> None:
        with pytest.raises(ValueError):
            AsyncBatchProgram()  # neither src nor file
        with pytest.raises(ValueError):
            AsyncBatchProgram("x", file="y")  # both

    asyncio.run(run())


# ----------------------------------------------------------------------
# Concurrency
# ----------------------------------------------------------------------


def test_two_async_sessions_run_in_parallel():
    """Two async sessions on independent thread pools complete via gather."""

    async def one(label: int) -> int:
        async with AsyncEasySession(".decl x(a: int32)\n") as s:
            await s.insert("x", [label])
            return label

    async def run() -> None:
        out = await asyncio.gather(one(1), one(2), one(3))
        assert set(out) == {1, 2, 3}

    asyncio.run(run())


def test_aclose_idempotent():
    async def run() -> None:
        s = AsyncEasySession(".decl x(a: int32)\n")
        await s.aclose()
        await s.aclose()

    asyncio.run(run())
