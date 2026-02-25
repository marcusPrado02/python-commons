"""Unit tests for §69 – Application Cache Invalidation."""
import asyncio

import pytest

from mp_commons.application.cache import (
    CacheInvalidationEvent,
    CacheKey,
    CacheWarmupService,
    InMemoryTaggedCacheStore,
    cached,
)


# ---------------------------------------------------------------------------
# CacheKey
# ---------------------------------------------------------------------------

class TestCacheKey:
    def test_for_resource_format(self):
        key = CacheKey.for_resource("order", "42")
        assert key == "order:42"

    def test_for_query_deterministic(self):
        k1 = CacheKey.for_query("products", category="shoes", page=1)
        k2 = CacheKey.for_query("products", page=1, category="shoes")
        assert k1 == k2

    def test_for_query_different_args(self):
        k1 = CacheKey.for_query("products", category="shoes")
        k2 = CacheKey.for_query("products", category="bags")
        assert k1 != k2

    def test_for_query_prefix(self):
        k = CacheKey.for_query("search", q="test")
        assert k.startswith("query:search:")


# ---------------------------------------------------------------------------
# InMemoryTaggedCacheStore
# ---------------------------------------------------------------------------

class TestTaggedCacheStore:
    def test_set_and_get(self):
        store = InMemoryTaggedCacheStore()
        asyncio.run(store.set("k1", "hello", ttl=60, tags=["tag-a"]))
        result = asyncio.run(store.get("k1"))
        assert result == "hello"

    def test_get_missing_returns_none(self):
        store = InMemoryTaggedCacheStore()
        assert asyncio.run(store.get("missing")) is None

    def test_delete(self):
        store = InMemoryTaggedCacheStore()
        asyncio.run(store.set("k1", "v", ttl=60, tags=[]))
        asyncio.run(store.delete("k1"))
        assert asyncio.run(store.get("k1")) is None

    def test_invalidate_tag_removes_keys(self):
        store = InMemoryTaggedCacheStore()
        asyncio.run(store.set("k1", "a", ttl=60, tags=["tag-x"]))
        asyncio.run(store.set("k2", "b", ttl=60, tags=["tag-x", "tag-y"]))
        asyncio.run(store.set("k3", "c", ttl=60, tags=["tag-y"]))
        removed = asyncio.run(store.invalidate_tag("tag-x"))
        assert removed == 2
        assert asyncio.run(store.get("k1")) is None
        assert asyncio.run(store.get("k2")) is None
        assert asyncio.run(store.get("k3")) == "c"

    def test_invalidate_returns_event(self):
        store = InMemoryTaggedCacheStore()
        asyncio.run(store.set("k1", "v", ttl=60, tags=["t"]))
        removed = asyncio.run(store.invalidate_tag("t"))
        assert removed == 1


# ---------------------------------------------------------------------------
# @cached decorator
# ---------------------------------------------------------------------------

class TestCachedDecorator:
    def test_result_cached_second_call(self):
        calls = []

        @cached(ttl=60, key_fn=lambda x: f"fn:{x}", tags=["grp"])
        async def compute(x: int) -> int:
            calls.append(x)
            return x * 2

        asyncio.run(compute(5))
        asyncio.run(compute(5))
        assert len(calls) == 1

    def test_different_keys_not_shared(self):
        calls = []

        @cached(ttl=60, key_fn=lambda x: f"fn:{x}", tags=[])
        async def compute(x: int) -> int:
            calls.append(x)
            return x * 2

        asyncio.run(compute(1))
        asyncio.run(compute(2))
        assert len(calls) == 2


# ---------------------------------------------------------------------------
# CacheWarmupService
# ---------------------------------------------------------------------------

class TestCacheWarmupService:
    def test_warm_loads_and_stores(self):
        store = InMemoryTaggedCacheStore()
        warmer = CacheWarmupService(store)
        warmer.register("top_products", lambda: asyncio.coroutine(lambda: ["p1", "p2"])())

        async def run():
            warmer.register("top_products", lambda: _coro())
            return await warmer.warm("top_products")

        async def _coro():
            return ["p1", "p2"]

        result = asyncio.run(run())
        assert result == ["p1", "p2"]
