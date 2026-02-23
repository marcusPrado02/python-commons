"""Unit tests for Redis adapters (§28.1–28.4) — no running Redis required."""
from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_cache() -> tuple[Any, MagicMock]:
    """Return (RedisCache, mock_client) without needing a real Redis."""
    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=None)
    mock_client.set = AsyncMock()
    mock_client.delete = AsyncMock()
    mock_client.exists = AsyncMock(return_value=0)
    mock_client.aclose = AsyncMock()

    import mp_commons.adapters.redis.cache as cache_mod

    mock_aioredis = MagicMock()
    mock_aioredis.from_url = MagicMock(return_value=mock_client)

    with patch.object(cache_mod, "_require_redis", return_value=mock_aioredis):
        from mp_commons.adapters.redis.cache import RedisCache
        cache = RedisCache("redis://localhost:6379")

    return cache, mock_client


def _make_pipeline_mock(count: int) -> MagicMock:
    pipe = MagicMock()
    pipe.incr = AsyncMock()
    pipe.expire = AsyncMock()
    pipe.execute = AsyncMock(return_value=(count, True))
    pipe.__aenter__ = AsyncMock(return_value=pipe)
    pipe.__aexit__ = AsyncMock(return_value=False)
    return pipe


def _idem_key() -> Any:
    from mp_commons.kernel.messaging import IdempotencyKey
    return IdempotencyKey(client_key="req-abc", operation="CreateOrder")


# ---------------------------------------------------------------------------
# §28.1 RedisCache
# ---------------------------------------------------------------------------


class TestRedisCache:
    def test_get_returns_none_on_miss(self) -> None:
        async def run() -> None:
            cache, client = _make_cache()
            client.get = AsyncMock(return_value=None)
            assert await cache.get("missing") is None
            client.get.assert_awaited_once_with("missing")
        asyncio.run(run())

    def test_get_returns_bytes_on_hit(self) -> None:
        async def run() -> None:
            cache, client = _make_cache()
            client.get = AsyncMock(return_value=b"hello")
            assert await cache.get("key") == b"hello"
        asyncio.run(run())

    def test_set_no_ttl(self) -> None:
        async def run() -> None:
            cache, client = _make_cache()
            client.set = AsyncMock()
            await cache.set("key", b"value")
            client.set.assert_awaited_once_with("key", b"value", ex=None)
        asyncio.run(run())

    def test_set_with_ttl(self) -> None:
        async def run() -> None:
            cache, client = _make_cache()
            client.set = AsyncMock()
            await cache.set("key", b"value", ttl=60)
            client.set.assert_awaited_once_with("key", b"value", ex=60)
        asyncio.run(run())

    def test_delete_delegates(self) -> None:
        async def run() -> None:
            cache, client = _make_cache()
            client.delete = AsyncMock()
            await cache.delete("key")
            client.delete.assert_awaited_once_with("key")
        asyncio.run(run())

    def test_exists_false(self) -> None:
        async def run() -> None:
            cache, client = _make_cache()
            client.exists = AsyncMock(return_value=0)
            assert await cache.exists("key") is False
        asyncio.run(run())

    def test_exists_true(self) -> None:
        async def run() -> None:
            cache, client = _make_cache()
            client.exists = AsyncMock(return_value=1)
            assert await cache.exists("key") is True
        asyncio.run(run())

    def test_close_calls_aclose(self) -> None:
        async def run() -> None:
            cache, client = _make_cache()
            client.aclose = AsyncMock()
            await cache.close()
            client.aclose.assert_awaited_once()
        asyncio.run(run())


# ---------------------------------------------------------------------------
# §28.2 RedisRateLimiter
# ---------------------------------------------------------------------------


class TestRedisRateLimiter:
    def _limiter_and_client(self, count: int) -> tuple[Any, MagicMock]:
        cache, client = _make_cache()
        client.pipeline = MagicMock(return_value=_make_pipeline_mock(count))
        from mp_commons.adapters.redis.rate_limiter import RedisRateLimiter
        return RedisRateLimiter(cache), client

    def test_check_allowed_when_under_limit(self) -> None:
        async def run() -> None:
            from mp_commons.application.rate_limit import Quota, RateLimitDecision
            limiter, _ = self._limiter_and_client(count=3)
            quota = Quota(key="api", limit=5, window_seconds=60)
            result = await limiter.check(quota, "user-1")
            assert result.decision == RateLimitDecision.ALLOWED
            assert result.remaining == 2
        asyncio.run(run())

    def test_check_denied_when_over_limit(self) -> None:
        async def run() -> None:
            from mp_commons.application.rate_limit import Quota, RateLimitDecision
            limiter, _ = self._limiter_and_client(count=6)
            quota = Quota(key="api", limit=5, window_seconds=60)
            result = await limiter.check(quota, "user-1")
            assert result.decision == RateLimitDecision.DENIED
            assert result.remaining == 0
        asyncio.run(run())

    def test_check_exactly_at_limit(self) -> None:
        async def run() -> None:
            from mp_commons.application.rate_limit import Quota, RateLimitDecision
            limiter, _ = self._limiter_and_client(count=5)
            quota = Quota(key="api", limit=5, window_seconds=60)
            result = await limiter.check(quota, "user-1")
            assert result.decision == RateLimitDecision.ALLOWED
            assert result.remaining == 0
        asyncio.run(run())

    def test_check_uses_correct_key(self) -> None:
        async def run() -> None:
            from mp_commons.application.rate_limit import Quota
            limiter, client = self._limiter_and_client(count=1)
            quota = Quota(key="search", limit=10, window_seconds=30)
            await limiter.check(quota, "alice")
            pipe = client.pipeline.return_value.__aenter__.return_value
            pipe.incr.assert_awaited_once_with("rl:search:alice")
        asyncio.run(run())

    def test_reset_deletes_key(self) -> None:
        async def run() -> None:
            from mp_commons.application.rate_limit import Quota
            limiter, client = self._limiter_and_client(count=0)
            client.delete = AsyncMock()
            quota = Quota(key="api", limit=5, window_seconds=60)
            await limiter.reset(quota, "user-42")
            client.delete.assert_awaited_once_with("rl:api:user-42")
        asyncio.run(run())

    def test_remaining_never_negative(self) -> None:
        async def run() -> None:
            from mp_commons.application.rate_limit import Quota
            limiter, _ = self._limiter_and_client(count=100)
            quota = Quota(key="api", limit=5, window_seconds=60)
            result = await limiter.check(quota, "user-1")
            assert result.remaining >= 0
        asyncio.run(run())


# ---------------------------------------------------------------------------
# §28.3 RedisLock
# ---------------------------------------------------------------------------


class TestRedisLock:
    def _lock(self, set_return: Any = True) -> tuple[Any, MagicMock]:
        cache, client = _make_cache()
        client.set = AsyncMock(return_value=set_return)
        client.eval = AsyncMock(return_value=1)
        from mp_commons.adapters.redis.lock import RedisLock
        return RedisLock(cache, "my-lock", ttl_ms=2000), client

    def test_acquire_success(self) -> None:
        async def run() -> None:
            lock, _ = self._lock(set_return=True)
            assert await lock.acquire() is True
            assert lock._token is not None  # noqa: SLF001
        asyncio.run(run())

    def test_acquire_failure(self) -> None:
        async def run() -> None:
            lock, _ = self._lock(set_return=None)
            assert await lock.acquire() is False
            assert lock._token is None  # noqa: SLF001
        asyncio.run(run())

    def test_release_calls_eval_and_clears_token(self) -> None:
        async def run() -> None:
            lock, client = self._lock(set_return=True)
            await lock.acquire()
            token = lock._token  # noqa: SLF001
            await lock.release()
            client.eval.assert_awaited_once()
            args = client.eval.await_args.args
            assert args[2] == "lock:my-lock"
            assert args[3] == token
            assert lock._token is None  # noqa: SLF001
        asyncio.run(run())

    def test_release_no_op_when_not_acquired(self) -> None:
        async def run() -> None:
            lock, client = self._lock(set_return=True)
            await lock.release()
            client.eval.assert_not_called()
        asyncio.run(run())

    def test_context_manager_happy_path(self) -> None:
        async def run() -> None:
            lock, _ = self._lock(set_return=True)
            async with lock as l:
                assert l is lock
                assert lock._token is not None  # noqa: SLF001
            assert lock._token is None  # noqa: SLF001
        asyncio.run(run())

    def test_context_manager_raises_conflict_on_failure(self) -> None:
        async def run() -> None:
            from mp_commons.kernel.errors import ConflictError
            lock, _ = self._lock(set_return=None)
            with pytest.raises(ConflictError):
                async with lock:
                    pass  # pragma: no cover
        asyncio.run(run())

    def test_set_called_with_nx_and_px(self) -> None:
        async def run() -> None:
            lock, client = self._lock(set_return=True)
            await lock.acquire()
            kw = client.set.await_args.kwargs
            assert kw.get("nx") is True
            assert kw.get("px") == 2000
        asyncio.run(run())

    def test_lock_name_prefixed(self) -> None:
        async def run() -> None:
            lock, client = self._lock(set_return=True)
            await lock.acquire()
            assert client.set.await_args.args[0] == "lock:my-lock"
        asyncio.run(run())


# ---------------------------------------------------------------------------
# §28.4 RedisIdempotencyStore
# ---------------------------------------------------------------------------


class TestRedisIdempotencyStore:
    def _store(self) -> tuple[Any, Any, MagicMock]:
        cache, client = _make_cache()
        from mp_commons.adapters.redis.idempotency import RedisIdempotencyStore
        return RedisIdempotencyStore(cache), cache, client

    def test_get_miss_returns_none(self) -> None:
        async def run() -> None:
            store, _, client = self._store()
            client.get = AsyncMock(return_value=None)
            assert await store.get(_idem_key()) is None
        asyncio.run(run())

    def test_get_hit_deserializes_record(self) -> None:
        async def run() -> None:
            store, _, client = self._store()
            key = _idem_key()
            payload = json.dumps({"key": str(key), "response": None, "status": "PROCESSING"}).encode()
            client.get = AsyncMock(return_value=payload)
            result = await store.get(key)
            assert result is not None
            assert result.status == "PROCESSING"
            assert result.response is None
        asyncio.run(run())

    def test_save_stores_json(self) -> None:
        async def run() -> None:
            store, _, client = self._store()
            from mp_commons.kernel.messaging import IdempotencyRecord
            client.set = AsyncMock()
            key = _idem_key()
            record = IdempotencyRecord(key=str(key))
            await store.save(key, record)
            client.set.assert_awaited_once()
            data = json.loads(client.set.await_args.args[1])
            assert data["status"] == "PROCESSING"
            assert data["response"] is None
        asyncio.run(run())

    def test_save_uses_correct_cache_key(self) -> None:
        async def run() -> None:
            store, _, client = self._store()
            from mp_commons.kernel.messaging import IdempotencyRecord
            client.set = AsyncMock()
            key = _idem_key()
            record = IdempotencyRecord(key=str(key))
            await store.save(key, record)
            assert client.set.await_args.args[0] == f"idempotency:{key}"
        asyncio.run(run())

    def test_complete_updates_status_to_completed(self) -> None:
        async def run() -> None:
            store, _, client = self._store()
            key = _idem_key()
            payload = json.dumps({"key": str(key), "response": None, "status": "PROCESSING"}).encode()
            client.get = AsyncMock(return_value=payload)
            client.set = AsyncMock()
            await store.complete(key, b"result-bytes")
            assert client.set.await_count == 1
            data = json.loads(client.set.await_args.args[1])
            assert data["status"] == "COMPLETED"
            assert data["response"] == "result-bytes"
        asyncio.run(run())

    def test_complete_no_op_when_key_missing(self) -> None:
        async def run() -> None:
            store, _, client = self._store()
            client.get = AsyncMock(return_value=None)
            client.set = AsyncMock()
            await store.complete(_idem_key(), b"whatever")
            client.set.assert_not_called()
        asyncio.run(run())

    def test_store_respects_default_ttl(self) -> None:
        async def run() -> None:
            store, _, client = self._store()
            from mp_commons.kernel.messaging import IdempotencyRecord
            client.set = AsyncMock()
            key = _idem_key()
            record = IdempotencyRecord(key=str(key))
            await store.save(key, record)
            # ttl passed as keyword or positional arg  
            call_args = client.set.await_args
            ttl = call_args.kwargs.get("ex") or (call_args.args[2] if len(call_args.args) > 2 else None)
            assert ttl == 86400
        asyncio.run(run())
