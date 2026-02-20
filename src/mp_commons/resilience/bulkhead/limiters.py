"""Resilience – ConcurrencyLimiter, QueueLimiter."""
from __future__ import annotations

import asyncio

from mp_commons.resilience.bulkhead.errors import BulkheadFullError


class ConcurrencyLimiter:
    """Limits the number of concurrent executions."""

    def __init__(self, max_concurrent: int) -> None:
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self.max_concurrent = max_concurrent

    @property
    def available(self) -> int:
        return self._semaphore._value  # noqa: SLF001

    async def __aenter__(self) -> "ConcurrencyLimiter":
        acquired = await asyncio.wait_for(self._semaphore.acquire(), timeout=0.01)
        if not acquired:
            raise BulkheadFullError("Concurrency limit reached")
        return self

    async def __aexit__(self, *_: object) -> None:
        self._semaphore.release()


class QueueLimiter:
    """Limits the number of waiting requests (queue depth)."""

    def __init__(self, max_concurrent: int, max_queue: int) -> None:
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._queue = asyncio.Semaphore(max_concurrent + max_queue)
        self.max_concurrent = max_concurrent
        self.max_queue = max_queue

    async def __aenter__(self) -> "QueueLimiter":
        if not self._queue._value:  # noqa: SLF001
            raise BulkheadFullError("Queue is full")
        await self._queue.acquire()
        await self._semaphore.acquire()
        return self

    async def __aexit__(self, *_: object) -> None:
        self._semaphore.release()
        self._queue.release()


__all__ = ["ConcurrencyLimiter", "QueueLimiter"]
