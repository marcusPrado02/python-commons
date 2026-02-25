"""Unit tests for §76 – Fallback Policy."""
import asyncio

import pytest

from mp_commons.resilience.fallback import CachedFallbackPolicy, FallbackPolicy


class TestFallbackPolicy:
    def test_success_path(self):
        async def fn():
            return 42

        policy = FallbackPolicy(fallback=lambda: asyncio.coroutine(lambda: -1)())
        # Override with proper coro factory
        async def fallback_fn():
            return -1

        policy2 = FallbackPolicy(fallback=fallback_fn)
        result = asyncio.run(policy2.execute(fn))
        assert result == 42

    def test_fallback_called_on_listed_exception(self):
        async def bad():
            raise ValueError("boom")

        async def fallback():
            return "safe"

        policy = FallbackPolicy(fallback=fallback, on_exceptions=(ValueError,))
        result = asyncio.run(policy.execute(bad))
        assert result == "safe"

    def test_unlisted_exception_propagates(self):
        async def bad():
            raise RuntimeError("unexpected")

        async def fallback():
            return "safe"

        policy = FallbackPolicy(fallback=fallback, on_exceptions=(ValueError,))
        with pytest.raises(RuntimeError):
            asyncio.run(policy.execute(bad))

    def test_static_fallback_value(self):
        async def bad():
            raise ValueError("x")

        policy = FallbackPolicy(fallback="default", on_exceptions=(ValueError,))
        result = asyncio.run(policy.execute(bad))
        assert result == "default"


class TestCachedFallbackPolicy:
    def test_caches_last_success(self):
        call_count = [0]

        async def fn():
            call_count[0] += 1
            return call_count[0]

        policy = CachedFallbackPolicy(fallback=lambda: None)
        asyncio.run(policy.execute(fn))
        assert policy.has_cached is True
        assert policy.cached_value == 1

    def test_serves_stale_on_failure(self):
        async def good():
            return "fresh"

        fail = [False]

        async def maybe_bad():
            if fail[0]:
                raise IOError("gone")
            return "fresh"

        async def fallback():
            return "ultimate"

        policy = CachedFallbackPolicy(fallback=fallback, on_exceptions=(IOError,))
        asyncio.run(policy.execute(maybe_bad))
        fail[0] = True
        result = asyncio.run(policy.execute(maybe_bad))
        assert result == "fresh"  # served stale cached value

    def test_no_cached_falls_to_fallback(self):
        async def bad():
            raise IOError("x")

        async def fallback():
            return "fallback"

        policy = CachedFallbackPolicy(fallback=fallback, on_exceptions=(IOError,))
        result = asyncio.run(policy.execute(bad))
        assert result == "fallback"

    def test_cached_value_raises_when_empty(self):
        policy = CachedFallbackPolicy(fallback="x")
        with pytest.raises(ValueError):
            _ = policy.cached_value
