from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Generic, TypeVar

__all__ = [
    "HedgePolicy",
    "HedgeResult",
]

T = TypeVar("T")


@dataclass
class HedgeResult(Generic[T]):
    value: T
    winner_index: int   # 0 = original, 1..N = hedge index
    latency_ms: float


class HedgePolicy(Generic[T]):
    """Fires the original request and (after *delay_ms*) a hedge copy.

    Returns the first successful result and cancels the others.
    """

    def __init__(self, delay_ms: float = 100.0, max_hedges: int = 1) -> None:
        self.delay_ms = delay_ms
        self.max_hedges = max_hedges

    async def execute(self, fn: Callable[[], Awaitable[T]]) -> HedgeResult[T]:
        started = time.monotonic()
        loop = asyncio.get_event_loop()
        queue: asyncio.Queue[tuple[int, Any, BaseException | None]] = asyncio.Queue()

        async def _run(index: int) -> None:
            if index > 0:
                await asyncio.sleep(self.delay_ms / 1000.0 * index)
            try:
                result = await fn()
                await queue.put((index, result, None))
            except Exception as exc:  # noqa: BLE001
                await queue.put((index, None, exc))

        total = 1 + self.max_hedges
        tasks = [loop.create_task(_run(i)) for i in range(total)]

        errors: list[BaseException] = []
        winner: HedgeResult[T] | None = None

        for _ in range(total):
            idx, val, exc = await queue.get()
            if exc is None:
                latency = (time.monotonic() - started) * 1000
                winner = HedgeResult(value=val, winner_index=idx, latency_ms=latency)
                break
            errors.append(exc)

        # Cancel remaining tasks
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

        if winner is not None:
            return winner
        raise errors[0]
