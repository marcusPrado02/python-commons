"""Unit tests for AsyncLRUCache (P-04)."""

from __future__ import annotations

import asyncio

import pytest

from mp_commons.application.cache.lru import AsyncLRUCache


class TestAsyncLRUCache:
    def test_rejects_invalid_maxsize(self):
        with pytest.raises(ValueError, match="maxsize"):
            AsyncLRUCache(maxsize=0)

    def test_initial_state(self):
        c = AsyncLRUCache(maxsize=10, ttl=60.0)
        assert c.maxsize == 10
        assert c.ttl == 60.0
        assert c.size == 0
        assert c.hits == 0
        assert c.misses == 0

    async def test_set_and_get(self):
        c = AsyncLRUCache(maxsize=5)
        await c.set("k", "v")
        assert await c.get("k") == "v"

    async def test_miss_returns_none(self):
        c = AsyncLRUCache(maxsize=5)
        assert await c.get("nonexistent") is None

    async def test_evicts_lru_on_overflow(self):
        c = AsyncLRUCache(maxsize=3)
        await c.set("a", 1)
        await c.set("b", 2)
        await c.set("c", 3)
        # Access "a" to make "b" the LRU
        await c.get("a")
        await c.set("d", 4)  # should evict "b"
        assert await c.get("b") is None
        assert await c.get("a") == 1
        assert await c.get("c") == 3
        assert await c.get("d") == 4

    async def test_ttl_expiry(self):
        c = AsyncLRUCache(maxsize=10, ttl=0.05)
        await c.set("k", "val")
        assert await c.get("k") == "val"
        await asyncio.sleep(0.1)
        assert await c.get("k") is None

    async def test_per_entry_ttl_overrides_cache_ttl(self):
        c = AsyncLRUCache(maxsize=10, ttl=3600.0)
        await c.set("short", "value", ttl=0.05)
        assert await c.get("short") == "value"
        await asyncio.sleep(0.1)
        assert await c.get("short") is None

    async def test_delete(self):
        c = AsyncLRUCache(maxsize=5)
        await c.set("k", "v")
        deleted = await c.delete("k")
        assert deleted
        assert await c.get("k") is None

    async def test_delete_nonexistent_returns_false(self):
        c = AsyncLRUCache(maxsize=5)
        assert not await c.delete("nope")

    async def test_clear(self):
        c = AsyncLRUCache(maxsize=5)
        await c.set("a", 1)
        await c.set("b", 2)
        await c.clear()
        assert c.size == 0
        assert await c.get("a") is None

    async def test_hit_rate(self):
        c = AsyncLRUCache(maxsize=5)
        await c.set("k", "v")
        await c.get("k")  # hit
        await c.get("k")  # hit
        await c.get("missing")  # miss
        assert c.hits == 2
        assert c.misses == 1
        assert c.hit_rate == pytest.approx(2 / 3)

    async def test_get_or_load_sync_loader(self):
        c = AsyncLRUCache(maxsize=5)
        calls: list[str] = []

        def loader(key: str) -> str:
            calls.append(key)
            return f"loaded-{key}"

        result = await c.get_or_load("x", loader, "x")
        assert result == "loaded-x"
        assert calls == ["x"]

        # Second call must not invoke loader again
        result2 = await c.get_or_load("x", loader, "x")
        assert result2 == "loaded-x"
        assert calls == ["x"]  # still only one call

    async def test_get_or_load_async_loader(self):
        c = AsyncLRUCache(maxsize=5)

        async def async_loader(key: str) -> str:
            return f"async-{key}"

        result = await c.get_or_load("y", async_loader, "y")
        assert result == "async-y"
        # cached on second call
        assert await c.get("y") == "async-y"

    async def test_concurrent_access_is_safe(self):
        c = AsyncLRUCache(maxsize=100)

        async def writer(n: int) -> None:
            await c.set(str(n), n)

        async def reader(n: int) -> None:
            await c.get(str(n))

        tasks = [writer(i) for i in range(50)] + [reader(i) for i in range(50)]
        await asyncio.gather(*tasks)

    def test_repr(self):
        c = AsyncLRUCache(maxsize=8, ttl=30.0)
        r = repr(c)
        assert "AsyncLRUCache" in r
        assert "8" in r
        assert "30.0" in r
