"""Unit tests for §93 – Performance Assertions."""
from __future__ import annotations

import asyncio

import pytest

from mp_commons.testing.performance import (
    PerformanceAssertionError,
    assert_completes_within,
    assert_memory_increase_below,
    assert_throughput,
)


class TestAssertCompletesWithin:
    def test_fast_coroutine_passes(self):
        async def fast():
            return 42

        result = asyncio.run(assert_completes_within(fast(), max_ms=5000))
        assert result == 42

    def test_slow_coroutine_fails(self):
        async def slow():
            import asyncio as _asyncio
            await _asyncio.sleep(0.2)

        with pytest.raises(PerformanceAssertionError, match="ms"):
            asyncio.run(assert_completes_within(slow(), max_ms=10))

    def test_returns_coro_result(self):
        async def returns_list():
            return [1, 2, 3]

        result = asyncio.run(assert_completes_within(returns_list(), max_ms=1000))
        assert result == [1, 2, 3]


class TestAssertThroughput:
    def test_fast_fn_meets_threshold(self):
        async def noop():
            pass

        rps = asyncio.run(assert_throughput(noop, min_ops_per_sec=100, duration_sec=0.1))
        assert rps >= 100

    def test_slow_fn_fails(self):
        async def slow():
            await asyncio.sleep(0.05)

        with pytest.raises(PerformanceAssertionError, match="ops/s"):
            asyncio.run(assert_throughput(slow, min_ops_per_sec=1000, duration_sec=0.1))

    def test_returns_actual_rps(self):
        async def noop():
            pass

        rps = asyncio.run(assert_throughput(noop, min_ops_per_sec=1, duration_sec=0.1))
        assert isinstance(rps, float)
        assert rps > 0


class TestAssertMemoryIncreaseBelow:
    def test_small_allocation_passes(self):
        def small():
            return list(range(10))

        result = assert_memory_increase_below(small, max_bytes=1_000_000)
        assert result == list(range(10))

    def test_large_allocation_fails(self):
        def large():
            return bytearray(10 * 1024 * 1024)  # 10 MB

        with pytest.raises(PerformanceAssertionError, match="bytes"):
            assert_memory_increase_below(large, max_bytes=100)

    def test_returns_fn_result(self):
        def compute():
            return {"answer": 42}

        result = assert_memory_increase_below(compute, max_bytes=10_000_000)
        assert result == {"answer": 42}
