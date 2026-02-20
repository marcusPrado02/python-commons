"""Redis adapter – RedisRateLimiter."""
from __future__ import annotations

from datetime import UTC, datetime

from mp_commons.application.rate_limit import Quota, RateLimitDecision, RateLimitResult, RateLimiter
from mp_commons.adapters.redis.cache import RedisCache


class RedisRateLimiter(RateLimiter):
    """Sliding-window rate limiter backed by Redis INCR + EXPIRE."""

    def __init__(self, cache: RedisCache) -> None:
        self._cache = cache

    async def check(self, quota: Quota, identifier: str) -> RateLimitResult:
        key = f"rl:{quota.key}:{identifier}"
        client = self._cache._client  # noqa: SLF001

        async with client.pipeline(transaction=True) as pipe:
            await pipe.incr(key)
            await pipe.expire(key, quota.window_seconds)
            count_raw, _ = await pipe.execute()

        count = int(count_raw)
        allowed = count <= quota.limit
        reset_at = datetime.now(UTC)

        return RateLimitResult(
            decision=RateLimitDecision.ALLOWED if allowed else RateLimitDecision.DENIED,
            remaining=max(0, quota.limit - count),
            reset_at=reset_at,
            quota=quota,
        )

    async def reset(self, quota: Quota, identifier: str) -> None:
        await self._cache.delete(f"rl:{quota.key}:{identifier}")


__all__ = ["RedisRateLimiter"]
