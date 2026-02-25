from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Generic, TypeVar

__all__ = [
    "ThrottledError",
    "ThrottlePolicy",
    "TokenBucket",
]

T = TypeVar("T")


class ThrottledError(Exception):
    """Raised when the token bucket is empty."""

    def __init__(self, retry_after_ms: float = 0.0) -> None:
        super().__init__(f"Rate limit exceeded – retry after {retry_after_ms:.0f} ms")
        self.retry_after_ms = retry_after_ms


@dataclass
class TokenBucket:
    """Token bucket rate limiter.

    *capacity* – maximum tokens.
    *refill_rate* – tokens added per second.
    """

    capacity: float
    refill_rate: float  # tokens / second
    _tokens: float = field(init=False)
    _last_refill: float = field(init=False)
    _lock: asyncio.Lock = field(init=False, compare=False, repr=False)

    def __post_init__(self) -> None:
        self._tokens = self.capacity
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self.capacity, self._tokens + elapsed * self.refill_rate)
        self._last_refill = now

    async def acquire(self, tokens: float = 1.0) -> bool:
        async with self._lock:
            self._refill()
            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False

    def retry_after_ms(self, tokens: float = 1.0) -> float:
        needed = tokens - self._tokens
        if needed <= 0:
            return 0.0
        if self.refill_rate <= 0:
            return float("inf")
        return (needed / self.refill_rate) * 1000.0


class ThrottlePolicy(Generic[T]):
    """Executes *fn* only when the token bucket has capacity."""

    def __init__(self, bucket: TokenBucket, tokens: float = 1.0) -> None:
        self._bucket = bucket
        self._tokens = tokens

    async def execute(self, fn: Callable[[], Awaitable[T]]) -> T:
        if not await self._bucket.acquire(self._tokens):
            retry_ms = self._bucket.retry_after_ms(self._tokens)
            raise ThrottledError(retry_ms)
        return await fn()
