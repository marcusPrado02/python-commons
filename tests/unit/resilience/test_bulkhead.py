"""Unit tests for Bulkhead pattern — §17."""

from __future__ import annotations

import asyncio

import pytest

from mp_commons.resilience.bulkhead import (
    Bulkhead,
    BulkheadFullError,
    ConcurrencyLimiter,
    QueueLimiter,
)


# ---------------------------------------------------------------------------
# BulkheadFullError (17.2)
# ---------------------------------------------------------------------------


class TestBulkheadFullError:
    def test_is_exception(self) -> None:
        err = BulkheadFullError("full")
        assert isinstance(err, Exception)

    def test_has_default_code(self) -> None:
        err = BulkheadFullError("full")
        assert err.default_code == "bulkhead_full"


# ---------------------------------------------------------------------------
# QueueLimiter (17.1 underlying)
# ---------------------------------------------------------------------------


class TestQueueLimiter:
    def test_normal_entry_exits_cleanly(self) -> None:
        async def run() -> None:
            lim = QueueLimiter(max_concurrent=2, max_queue=2)
            async with lim:
                pass  # no error

        asyncio.run(run())

    def test_overflow_raises_bulkhead_full(self) -> None:
        async def run() -> None:
            # max_concurrent=1, max_queue=0 → total capacity = 1
            lim = QueueLimiter(max_concurrent=1, max_queue=0)
            async with lim:
                # while inside, second attempt should fail immediately
                with pytest.raises(BulkheadFullError):
                    async with lim:
                        pass

        asyncio.run(run())

    def test_queue_capacity_overflow_with_concurrent_tasks(self) -> None:
        """With max_concurrent=1, max_queue=0: second concurrent request fails immediately."""
        async def run() -> None:
            lim = QueueLimiter(max_concurrent=1, max_queue=0)
            task_started = asyncio.Event()
            task_should_exit = asyncio.Event()

            async def holder() -> None:
                async with lim:
                    task_started.set()
                    await task_should_exit.wait()

            t = asyncio.create_task(holder())
            await task_started.wait()
            # lim is now held → _queue value is 0 → immediate rejection
            with pytest.raises(BulkheadFullError):
                async with lim:
                    pass
            task_should_exit.set()
            await t

        asyncio.run(run())

    def test_release_allows_reuse(self) -> None:
        async def run() -> None:
            lim = QueueLimiter(max_concurrent=1, max_queue=0)
            async with lim:
                pass
            # After exiting, should be usable again
            async with lim:
                pass

        asyncio.run(run())


# ---------------------------------------------------------------------------
# Bulkhead composite (17.1)
# ---------------------------------------------------------------------------


class TestBulkhead:
    def test_normal_entry_exits_cleanly(self) -> None:
        async def run() -> None:
            bh = Bulkhead(name="svc", max_concurrent=2, max_queue=2)
            async with bh:
                pass

        asyncio.run(run())

    def test_overflow_raises_bulkhead_full(self) -> None:
        async def run() -> None:
            bh = Bulkhead(name="svc", max_concurrent=1, max_queue=0)
            async with bh:
                with pytest.raises(BulkheadFullError):
                    async with bh:
                        pass

        asyncio.run(run())

    def test_sequential_reuse(self) -> None:
        async def run() -> None:
            bh = Bulkhead(name="svc", max_concurrent=1, max_queue=0)
            for _ in range(3):
                async with bh:
                    pass  # each entry and exit succeeds

        asyncio.run(run())

    def test_concurrent_within_limit(self) -> None:
        async def run() -> None:
            results: list[int] = []
            bh = Bulkhead(name="svc", max_concurrent=3, max_queue=0)

            async def worker(i: int) -> None:
                async with bh:
                    await asyncio.sleep(0)
                    results.append(i)

            await asyncio.gather(worker(1), worker(2), worker(3))
            assert sorted(results) == [1, 2, 3]

        asyncio.run(run())

    def test_name_stored(self) -> None:
        bh = Bulkhead(name="my-service", max_concurrent=5)
        assert bh.name == "my-service"


# ---------------------------------------------------------------------------
# Public surface smoke test
# ---------------------------------------------------------------------------


class TestPublicReExports:
    def test_all_symbols_importable(self) -> None:
        import importlib

        mod = importlib.import_module("mp_commons.resilience.bulkhead")
        for name in mod.__all__:
            assert hasattr(mod, name), f"{name!r} missing"
