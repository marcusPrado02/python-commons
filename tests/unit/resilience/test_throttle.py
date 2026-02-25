"""Unit tests for §79 – Token Bucket / Throttle."""
import asyncio

import pytest

from mp_commons.resilience.throttle import ThrottlePolicy, ThrottledError, TokenBucket


class TestTokenBucket:
    def test_acquire_within_capacity(self):
        bucket = TokenBucket(capacity=5, refill_rate=1)
        for _ in range(5):
            ok = asyncio.run(bucket.acquire())
            assert ok is True

    def test_acquire_exceeds_capacity(self):
        bucket = TokenBucket(capacity=2, refill_rate=0)  # no refill
        asyncio.run(bucket.acquire())
        asyncio.run(bucket.acquire())
        ok = asyncio.run(bucket.acquire())
        assert ok is False

    def test_retry_after_ms_positive_when_empty(self):
        bucket = TokenBucket(capacity=1, refill_rate=10)  # 10 tokens/s = 100ms per token
        asyncio.run(bucket.acquire())
        retry = bucket.retry_after_ms()
        assert retry > 0

    def test_refill_over_time(self):
        """After heavy use, tokens eventually refill (near-zero sleep)."""
        bucket = TokenBucket(capacity=1, refill_rate=1000)  # 1000 t/s
        asyncio.run(bucket.acquire())
        # Wait a tiny bit for refill
        import time; time.sleep(0.002)  # noqa: E401, E702
        ok = asyncio.run(bucket.acquire())
        assert ok is True


class TestThrottlePolicy:
    def test_executes_within_capacity(self):
        bucket = TokenBucket(capacity=3, refill_rate=1)
        policy = ThrottlePolicy(bucket)

        async def fn():
            return "ok"

        result = asyncio.run(policy.execute(fn))
        assert result == "ok"

    def test_raises_throttled_error_when_empty(self):
        bucket = TokenBucket(capacity=1, refill_rate=1)  # 1 token/s
        asyncio.run(bucket.acquire())  # drain
        policy = ThrottlePolicy(bucket)

        async def fn():
            return "x"

        with pytest.raises(ThrottledError) as exc_info:
            asyncio.run(policy.execute(fn))
        assert exc_info.value.retry_after_ms > 0

    def test_throttled_error_message(self):
        err = ThrottledError(retry_after_ms=500)
        assert "500" in str(err)
