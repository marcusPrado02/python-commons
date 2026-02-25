"""Integration tests for Redis adapters (§28.5).

Uses testcontainers to spawn a real Redis instance.
Run with: PYTHONPATH=src pytest tests/integration/test_redis.py -m integration -v
"""
from __future__ import annotations

import asyncio

import pytest
from testcontainers.redis import RedisContainer

from mp_commons.adapters.redis import (
    RedisCache,
    RedisIdempotencyStore,
    RedisLock,
    RedisRateLimiter,
)
from mp_commons.application.rate_limit import Quota, RateLimitDecision
from mp_commons.kernel.errors import ConflictError
from mp_commons.kernel.messaging import IdempotencyKey, IdempotencyRecord


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _run(coro):  # type: ignore[no-untyped-def]
    return asyncio.run(coro)


def _redis_url(container) -> str:  # type: ignore[no-untyped-def]
    host = container.get_container_host_ip()
    port = container.get_exposed_port(container.port)
    return f"redis://{host}:{port}/0"


# ---------------------------------------------------------------------------
# §28.5 – RedisRateLimiter
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestRedisRateLimiterIntegration:
    """Real Redis rate-limiter tests."""

    def test_allows_requests_within_limit(self) -> None:
        with RedisContainer() as container:
            url = _redis_url(container)

            async def run() -> None:
                cache = RedisCache(url=url)
                limiter = RedisRateLimiter(cache)
                quota = Quota(key="api", limit=3, window_seconds=60)
                for _ in range(3):
                    result = await limiter.check(quota, "user-1")
                    assert result.decision == RateLimitDecision.ALLOWED
                await cache.close()

            _run(run())

    def test_denies_request_exceeding_limit(self) -> None:
        with RedisContainer() as container:
            url = _redis_url(container)

            async def run() -> None:
                cache = RedisCache(url=url)
                limiter = RedisRateLimiter(cache)
                quota = Quota(key="api", limit=2, window_seconds=60)
                await limiter.check(quota, "user-2")
                await limiter.check(quota, "user-2")
                result = await limiter.check(quota, "user-2")
                assert result.decision == RateLimitDecision.DENIED
                assert result.remaining == 0
                await cache.close()

            _run(run())

    def test_remaining_decrements_as_requests_consumed(self) -> None:
        with RedisContainer() as container:
            url = _redis_url(container)

            async def run() -> None:
                cache = RedisCache(url=url)
                limiter = RedisRateLimiter(cache)
                quota = Quota(key="dec", limit=5, window_seconds=60)
                r1 = await limiter.check(quota, "user-3")
                r2 = await limiter.check(quota, "user-3")
                assert r1.remaining == 4
                assert r2.remaining == 3
                await cache.close()

            _run(run())

    def test_reset_clears_counter(self) -> None:
        with RedisContainer() as container:
            url = _redis_url(container)

            async def run() -> None:
                cache = RedisCache(url=url)
                limiter = RedisRateLimiter(cache)
                quota = Quota(key="rst", limit=1, window_seconds=60)
                # exhaust the quota
                await limiter.check(quota, "user-4")
                denied = await limiter.check(quota, "user-4")
                assert denied.decision == RateLimitDecision.DENIED
                # reset and try again
                await limiter.reset(quota, "user-4")
                allowed = await limiter.check(quota, "user-4")
                assert allowed.decision == RateLimitDecision.ALLOWED
                await cache.close()

            _run(run())

    def test_different_identifiers_have_independent_counters(self) -> None:
        with RedisContainer() as container:
            url = _redis_url(container)

            async def run() -> None:
                cache = RedisCache(url=url)
                limiter = RedisRateLimiter(cache)
                quota = Quota(key="ind", limit=1, window_seconds=60)
                await limiter.check(quota, "user-a")
                denied = await limiter.check(quota, "user-a")
                assert denied.decision == RateLimitDecision.DENIED
                # user-b still has full quota
                allowed = await limiter.check(quota, "user-b")
                assert allowed.decision == RateLimitDecision.ALLOWED
                await cache.close()

            _run(run())


# ---------------------------------------------------------------------------
# §28.5 – RedisLock
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestRedisLockIntegration:
    """Real Redis distributed lock tests."""

    def test_acquire_returns_true_when_unlocked(self) -> None:
        with RedisContainer() as container:
            url = _redis_url(container)

            async def run() -> None:
                cache = RedisCache(url=url)
                lock = RedisLock(cache, name="res-1", ttl_ms=5000)
                acquired = await lock.acquire()
                assert acquired is True
                await lock.release()
                await cache.close()

            _run(run())

    def test_second_acquire_returns_false(self) -> None:
        with RedisContainer() as container:
            url = _redis_url(container)

            async def run() -> None:
                cache = RedisCache(url=url)
                lock1 = RedisLock(cache, name="res-2", ttl_ms=5000)
                lock2 = RedisLock(cache, name="res-2", ttl_ms=5000)
                assert await lock1.acquire() is True
                assert await lock2.acquire() is False
                await lock1.release()
                await cache.close()

            _run(run())

    def test_release_allows_reacquire(self) -> None:
        with RedisContainer() as container:
            url = _redis_url(container)

            async def run() -> None:
                cache = RedisCache(url=url)
                lock = RedisLock(cache, name="res-3", ttl_ms=5000)
                await lock.acquire()
                await lock.release()
                # Fresh lock on same resource can now be acquired
                lock2 = RedisLock(cache, name="res-3", ttl_ms=5000)
                assert await lock2.acquire() is True
                await lock2.release()
                await cache.close()

            _run(run())

    def test_context_manager_acquires_and_releases(self) -> None:
        with RedisContainer() as container:
            url = _redis_url(container)

            async def run() -> None:
                cache = RedisCache(url=url)
                async with RedisLock(cache, name="res-4", ttl_ms=5000):
                    # inside: lock is held
                    inner = RedisLock(cache, name="res-4", ttl_ms=5000)
                    assert await inner.acquire() is False
                # outside: lock should be released
                outer = RedisLock(cache, name="res-4", ttl_ms=5000)
                assert await outer.acquire() is True
                await outer.release()
                await cache.close()

            _run(run())

    def test_context_manager_raises_conflict_when_already_locked(self) -> None:
        with RedisContainer() as container:
            url = _redis_url(container)

            async def run() -> None:
                cache = RedisCache(url=url)
                holder = RedisLock(cache, name="res-5", ttl_ms=5000)
                await holder.acquire()
                with pytest.raises(ConflictError):
                    async with RedisLock(cache, name="res-5", ttl_ms=5000):
                        pass  # pragma: no cover
                await holder.release()
                await cache.close()

            _run(run())


# ---------------------------------------------------------------------------
# §28.5 – RedisIdempotencyStore
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestRedisIdempotencyStoreIntegration:
    """Real Redis idempotency store tests."""

    def test_get_unknown_key_returns_none(self) -> None:
        with RedisContainer() as container:
            url = _redis_url(container)

            async def run() -> None:
                cache = RedisCache(url=url)
                store = RedisIdempotencyStore(cache)
                key = IdempotencyKey(client_key="x", operation="op")
                assert await store.get(key) is None
                await cache.close()

            _run(run())

    def test_save_and_get_roundtrip(self) -> None:
        with RedisContainer() as container:
            url = _redis_url(container)

            async def run() -> None:
                cache = RedisCache(url=url)
                store = RedisIdempotencyStore(cache)
                key = IdempotencyKey(client_key="req-1", operation="create-order")
                record = IdempotencyRecord(key=str(key), response=None, status="PROCESSING")
                await store.save(key, record)
                fetched = await store.get(key)
                assert fetched is not None
                assert fetched.key == str(key)
                assert fetched.status == "PROCESSING"
                await cache.close()

            _run(run())

    def test_complete_sets_response_and_completed_status(self) -> None:
        with RedisContainer() as container:
            url = _redis_url(container)

            async def run() -> None:
                cache = RedisCache(url=url)
                store = RedisIdempotencyStore(cache)
                key = IdempotencyKey(client_key="req-2", operation="place-order")
                record = IdempotencyRecord(key=str(key), response=None, status="PROCESSING")
                await store.save(key, record)
                await store.complete(key, b'{"ok": true}')
                fetched = await store.get(key)
                assert fetched is not None
                assert fetched.status == "COMPLETED"
                assert fetched.response == '{"ok": true}'
                await cache.close()

            _run(run())

    def test_complete_on_missing_key_is_noop(self) -> None:
        with RedisContainer() as container:
            url = _redis_url(container)

            async def run() -> None:
                cache = RedisCache(url=url)
                store = RedisIdempotencyStore(cache)
                key = IdempotencyKey(client_key="ghost", operation="op")
                # should not raise
                await store.complete(key, b"response")
                await cache.close()

            _run(run())

    def test_different_keys_are_independent(self) -> None:
        with RedisContainer() as container:
            url = _redis_url(container)

            async def run() -> None:
                cache = RedisCache(url=url)
                store = RedisIdempotencyStore(cache)
                k1 = IdempotencyKey(client_key="r1", operation="op")
                k2 = IdempotencyKey(client_key="r2", operation="op")
                r1 = IdempotencyRecord(key=str(k1), response=None, status="PROCESSING")
                await store.save(k1, r1)
                assert await store.get(k2) is None
                await cache.close()

            _run(run())
