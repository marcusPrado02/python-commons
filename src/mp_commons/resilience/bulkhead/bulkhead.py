"""Resilience – Bulkhead composite."""
from __future__ import annotations
from mp_commons.resilience.bulkhead.limiters import QueueLimiter


class Bulkhead:
    """Composite bulkhead combining concurrency + queue limiting."""

    def __init__(self, name: str, max_concurrent: int = 10, max_queue: int = 5) -> None:
        self.name = name
        self._limiter = QueueLimiter(max_concurrent, max_queue)

    async def __aenter__(self) -> "Bulkhead":
        await self._limiter.__aenter__()
        return self

    async def __aexit__(self, *args: object) -> None:
        await self._limiter.__aexit__(*args)


__all__ = ["Bulkhead"]
