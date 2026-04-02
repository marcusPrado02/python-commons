"""P-02 — Benchmark: RedisRateLimiter.check() latency.

This benchmark runs against an in-memory fake so it measures pure Python
overhead rather than network RTT.  The real-Redis p99 < 5 ms target is
validated in integration tests (test_redis.py).

Measures per-check() overhead with varying concurrency levels.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from mp_commons.adapters.redis import RedisRateLimiter
from mp_commons.application.rate_limit import Quota, RateLimitDecision

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_cache_mock() -> MagicMock:
    """Return a RedisCache mock whose pipeline always allows requests."""
    pipe = AsyncMock()
    # pipeline.execute() returns (count, expire_result)
    pipe.execute = AsyncMock(return_value=(1, 1))
    pipe.incr = AsyncMock()
    pipe.expire = AsyncMock()
    pipe.__aenter__ = AsyncMock(return_value=pipe)
    pipe.__aexit__ = AsyncMock(return_value=None)

    client = MagicMock()
    client.pipeline = MagicMock(return_value=pipe)

    cache = MagicMock()
    cache._client = client
    return cache


def _make_limiter() -> RedisRateLimiter:
    return RedisRateLimiter(cache=_make_cache_mock())


def _make_quota() -> Quota:
    return Quota(key="api", limit=1000, window_seconds=60)


# ---------------------------------------------------------------------------
# Benchmarks
# ---------------------------------------------------------------------------


def test_rate_limiter_single_check(benchmark: Any, event_loop: Any) -> None:
    """Single check() call — measures pure per-call overhead."""
    limiter = _make_limiter()
    quota = _make_quota()

    def run() -> Any:
        return event_loop.run_until_complete(limiter.check(quota, "user:1"))

    result = benchmark(run)
    assert result.decision == RateLimitDecision.ALLOWED


def test_rate_limiter_10_concurrent_checks(benchmark: Any, event_loop: Any) -> None:
    """10 concurrent check() calls — models a moderate request burst."""
    limiter = _make_limiter()
    quota = _make_quota()

    async def _batch() -> list[Any]:
        return await asyncio.gather(*[limiter.check(quota, "user:burst") for _ in range(10)])

    def run() -> list[Any]:
        return event_loop.run_until_complete(_batch())

    results = benchmark(run)
    assert len(results) == 10
    assert all(r.decision == RateLimitDecision.ALLOWED for r in results)


def test_rate_limiter_100_concurrent_checks(benchmark: Any, event_loop: Any) -> None:
    """100 concurrent check() calls — high-concurrency burst."""
    limiter = _make_limiter()
    quota = _make_quota()

    async def _batch() -> list[Any]:
        return await asyncio.gather(*[limiter.check(quota, "user:heavy") for _ in range(100)])

    def run() -> list[Any]:
        return event_loop.run_until_complete(_batch())

    results = benchmark(run)
    assert len(results) == 100
    assert all(r.decision == RateLimitDecision.ALLOWED for r in results)
