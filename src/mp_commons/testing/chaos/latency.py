"""Testing chaos – LatencyInjector."""
from __future__ import annotations

import asyncio
import random


class LatencyInjector:
    """Inject random artificial latency into async calls."""

    def __init__(self, min_ms: float = 50.0, max_ms: float = 500.0) -> None:
        self._min = min_ms / 1000
        self._max = max_ms / 1000

    async def call(self, coro: object) -> object:
        delay = random.uniform(self._min, self._max)  # noqa: S311
        await asyncio.sleep(delay)
        import asyncio as _asyncio
        import inspect
        if inspect.isawaitable(coro):
            return await coro  # type: ignore[misc]
        return coro


__all__ = ["LatencyInjector"]
