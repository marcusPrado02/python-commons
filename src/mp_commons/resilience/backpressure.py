"""Resilience – Backpressure policy.

:class:`BackpressurePolicy` limits the number of concurrently in-flight
coroutines (e.g., dispatched commands or handler tasks).  When the in-flight
count reaches *max_in_flight*, acquiring a slot raises :class:`BackpressureError`
immediately rather than blocking, giving callers a chance to shed load.

Usage::

    policy = BackpressurePolicy(max_in_flight=50)


    async def handle_request():
        async with policy:  # raises BackpressureError if overloaded
            await do_work()


    # or lower-level:
    async with policy.acquire():
        await do_work()

    # introspect:
    print(policy.in_flight)  # current in-flight count
    print(policy.utilization)  # 0.0 – 1.0
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager


class BackpressureError(Exception):
    """Raised when the in-flight limit is exceeded.

    Attributes
    ----------
    in_flight:
        Number of in-flight operations at the moment the error was raised.
    max_in_flight:
        The configured limit.
    """

    def __init__(self, in_flight: int, max_in_flight: int) -> None:
        super().__init__(f"Backpressure limit reached: {in_flight}/{max_in_flight} slots in use")
        self.in_flight = in_flight
        self.max_in_flight = max_in_flight


class BackpressurePolicy:
    """Non-blocking in-flight concurrency limiter.

    Unlike :class:`~mp_commons.resilience.bulkhead.ConcurrencyLimiter` which
    *queues* callers up to a configurable depth, :class:`BackpressurePolicy`
    always fails fast: if a slot is unavailable the caller receives
    :class:`BackpressureError` immediately.

    Parameters
    ----------
    max_in_flight:
        Maximum number of concurrent in-flight operations.  Must be ≥ 1.
    """

    def __init__(self, max_in_flight: int) -> None:
        if max_in_flight < 1:
            raise ValueError(f"max_in_flight must be >= 1, got {max_in_flight}")
        self._max = max_in_flight
        self._semaphore = asyncio.Semaphore(max_in_flight)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def max_in_flight(self) -> int:
        """The configured maximum number of in-flight operations."""
        return self._max

    @property
    def in_flight(self) -> int:
        """Current number of in-flight operations."""
        # Semaphore._value is the *available* slots; in-flight = max - available
        return self._max - self._semaphore._value  # type: ignore[attr-defined]

    @property
    def utilization(self) -> float:
        """Current load as a fraction of *max_in_flight* (0.0 – 1.0)."""
        return self.in_flight / self._max

    @property
    def is_overloaded(self) -> bool:
        """``True`` when the in-flight count equals *max_in_flight*."""
        return self._semaphore._value == 0  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # Context manager API
    # ------------------------------------------------------------------

    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[None]:
        """Acquire a slot or raise :class:`BackpressureError` immediately.

        Use as an async context manager::

            async with policy.acquire():
                await do_work()
        """
        acquired = self._semaphore.locked() is not True and self._semaphore._value > 0  # type: ignore[attr-defined]
        if not acquired:
            raise BackpressureError(self.in_flight, self._max)
        # Non-blocking acquire — we checked availability above; this should
        # not block, but use acquire() to be thread-safe.
        ok = await asyncio.wait_for(self._semaphore.acquire(), timeout=0)
        if not ok:
            raise BackpressureError(self.in_flight, self._max)
        try:
            yield
        finally:
            self._semaphore.release()

    async def __aenter__(self) -> BackpressurePolicy:
        if self._semaphore._value == 0:  # type: ignore[attr-defined]
            raise BackpressureError(self.in_flight, self._max)
        await self._semaphore.acquire()
        return self

    async def __aexit__(self, *_: object) -> None:
        self._semaphore.release()

    def __repr__(self) -> str:
        return f"BackpressurePolicy(max_in_flight={self._max}, in_flight={self.in_flight})"


__all__ = ["BackpressureError", "BackpressurePolicy"]
