"""Unit tests for BackpressurePolicy (R-01)."""

from __future__ import annotations

import asyncio

import pytest

from mp_commons.resilience.backpressure import BackpressureError, BackpressurePolicy


class TestBackpressurePolicy:
    def test_rejects_invalid_max(self):
        with pytest.raises(ValueError, match="max_in_flight"):
            BackpressurePolicy(max_in_flight=0)

    def test_initial_state(self):
        policy = BackpressurePolicy(max_in_flight=5)
        assert policy.max_in_flight == 5
        assert policy.in_flight == 0
        assert policy.utilization == 0.0
        assert not policy.is_overloaded

    async def test_acquires_slot(self):
        policy = BackpressurePolicy(max_in_flight=3)
        async with policy:
            assert policy.in_flight == 1
        assert policy.in_flight == 0

    async def test_raises_when_full(self):
        policy = BackpressurePolicy(max_in_flight=2)
        async with policy, policy:
            assert policy.in_flight == 2
            assert policy.is_overloaded
            with pytest.raises(BackpressureError) as exc_info:
                async with policy:
                    pass
            assert exc_info.value.in_flight == 2
            assert exc_info.value.max_in_flight == 2

    async def test_slot_released_after_exception(self):
        policy = BackpressurePolicy(max_in_flight=1)
        with pytest.raises(RuntimeError):
            async with policy:
                raise RuntimeError("oops")
        assert policy.in_flight == 0

    async def test_utilization(self):
        policy = BackpressurePolicy(max_in_flight=4)
        async with policy, policy:
            assert policy.utilization == pytest.approx(0.5)

    async def test_concurrent_slots(self):
        policy = BackpressurePolicy(max_in_flight=5)
        results: list[int] = []

        async def task(n: int) -> None:
            async with policy:
                await asyncio.sleep(0)
                results.append(n)

        await asyncio.gather(*[task(i) for i in range(5)])
        assert sorted(results) == list(range(5))

    async def test_backpressure_error_message(self):
        policy = BackpressurePolicy(max_in_flight=1)
        async with policy:
            with pytest.raises(BackpressureError, match="1/1 slots in use"):
                async with policy:
                    pass

    def test_repr(self):
        policy = BackpressurePolicy(max_in_flight=10)
        assert "10" in repr(policy)
        assert "BackpressurePolicy" in repr(policy)
