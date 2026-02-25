"""Unit tests for §78 – Cache-Aside Policy."""
import asyncio

import pytest

from mp_commons.resilience.cache import CacheAsidePolicy


class _InMemCache:
    def __init__(self):
        self._store: dict = {}

    async def get(self, key: str):
        return self._store.get(key)

    async def set(self, key: str, value, ttl: float) -> None:
        self._store[key] = value


class TestCacheAsidePolicy:
    def test_miss_calls_loader(self):
        cache = _InMemCache()
        policy = CacheAsidePolicy(cache, ttl=60)
        calls = []

        async def loader():
            calls.append(1)
            return "data"

        result = asyncio.run(policy.get_or_load("key1", loader))
        assert result == "data"
        assert len(calls) == 1

    def test_hit_skips_loader(self):
        cache = _InMemCache()
        policy = CacheAsidePolicy(cache, ttl=60)
        calls = []

        async def loader():
            calls.append(1)
            return "data"

        asyncio.run(policy.get_or_load("key1", loader))
        asyncio.run(policy.get_or_load("key1", loader))
        assert len(calls) == 1

    def test_different_keys_independent(self):
        cache = _InMemCache()
        policy = CacheAsidePolicy(cache, ttl=60)
        loads = []

        async def loader_a():
            loads.append("a")
            return "A"

        async def loader_b():
            loads.append("b")
            return "B"

        r_a = asyncio.run(policy.get_or_load("ka", loader_a))
        r_b = asyncio.run(policy.get_or_load("kb", loader_b))
        assert r_a == "A"
        assert r_b == "B"
        assert loads == ["a", "b"]

    def test_stampede_protection(self):
        """Two concurrent requests for same missing key should load once."""
        cache = _InMemCache()
        policy = CacheAsidePolicy(cache, ttl=60)
        calls = []

        async def loader():
            calls.append(1)
            await asyncio.sleep(0)
            return "val"

        async def run_both():
            t1 = asyncio.create_task(policy.get_or_load("x", loader))
            t2 = asyncio.create_task(policy.get_or_load("x", loader))
            return await asyncio.gather(t1, t2)

        results = asyncio.run(run_both())
        assert all(r == "val" for r in results)
        assert len(calls) == 1
