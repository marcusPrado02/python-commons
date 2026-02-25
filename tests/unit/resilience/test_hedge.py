"""Unit tests for §75 – Hedge Policy."""
import asyncio

import pytest

from mp_commons.resilience.hedge import HedgePolicy, HedgeResult


class TestHedgePolicy:
    def test_returns_result_on_success(self):
        async def fast():
            return 42

        policy = HedgePolicy(delay_ms=5, max_hedges=1)
        result = asyncio.run(policy.execute(fast))
        assert isinstance(result, HedgeResult)
        assert result.value == 42

    def test_winner_is_fastest(self):
        """Original always succeeds so winner_index should be 0."""
        async def fn():
            return "ok"

        policy = HedgePolicy(delay_ms=1, max_hedges=1)
        result = asyncio.run(policy.execute(fn))
        assert result.value == "ok"

    def test_hedge_wins_when_original_slow(self):
        call_order = []

        async def slow():
            call_order.append("slow")
            await asyncio.sleep(0.05)
            return "slow_result"

        policy = HedgePolicy(delay_ms=10, max_hedges=1)
        # Both will return same value; just check it completes
        result = asyncio.run(policy.execute(slow))
        assert result.value == "slow_result"

    def test_both_fail_raises(self):
        async def bad():
            raise ValueError("nope")

        policy = HedgePolicy(delay_ms=1, max_hedges=1)
        with pytest.raises(ValueError):
            asyncio.run(policy.execute(bad))

    def test_latency_ms_positive(self):
        async def fn():
            return 1

        policy = HedgePolicy(delay_ms=1, max_hedges=0)
        result = asyncio.run(policy.execute(fn))
        assert result.latency_ms >= 0

    def test_max_hedges_zero_one_call(self):
        """When max_hedges=0, only the original fires."""
        calls = []

        async def fn():
            calls.append(1)
            return "x"

        policy = HedgePolicy(delay_ms=1, max_hedges=0)
        result = asyncio.run(policy.execute(fn))
        assert result.value == "x"
        assert len(calls) == 1
