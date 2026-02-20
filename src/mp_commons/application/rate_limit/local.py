"""Application rate limiting – in-memory token-bucket implementation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from mp_commons.application.rate_limit.rate_limiter import (
    Quota,
    RateLimitDecision,
    RateLimitResult,
    RateLimiter,
)


class LocalTokenBucketRateLimiter(RateLimiter):
    """Single-process token-bucket rate limiter.

    Tracks request counts per ``(quota.key, identifier)`` pair.  The window
    resets once ``quota.window_seconds`` have elapsed since the first request
    in that window.
    """

    def __init__(self) -> None:
        # key -> (count_used, window_start)
        self._buckets: dict[str, tuple[int, datetime]] = {}

    def _key(self, quota: Quota, identifier: str) -> str:
        return f"{quota.key}:{identifier}"

    async def check(self, quota: Quota, identifier: str) -> RateLimitResult:
        key = self._key(quota, identifier)
        now = datetime.now(UTC)
        count, window_start = self._buckets.get(key, (0, now))

        # reset window if expired
        if (now - window_start).total_seconds() >= quota.window_seconds:
            count = 0
            window_start = now

        reset_at = window_start + timedelta(seconds=quota.window_seconds)

        if count < quota.limit:
            self._buckets[key] = (count + 1, window_start)
            return RateLimitResult(
                decision=RateLimitDecision.ALLOWED,
                remaining=quota.limit - count - 1,
                reset_at=reset_at,
                quota=quota,
            )

        return RateLimitResult(
            decision=RateLimitDecision.DENIED,
            remaining=0,
            reset_at=reset_at,
            quota=quota,
        )

    async def reset(self, quota: Quota, identifier: str) -> None:
        self._buckets.pop(self._key(quota, identifier), None)


__all__ = ["LocalTokenBucketRateLimiter"]
