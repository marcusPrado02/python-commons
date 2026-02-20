"""Unit tests for RetryPolicy and backoff strategies."""

from __future__ import annotations

import asyncio

import pytest

from mp_commons.resilience.retry import (
    ConstantBackoff,
    ExponentialBackoff,
    FullJitter,
    LinearBackoff,
    NoJitter,
    RetryPolicy,
)


# ---------------------------------------------------------------------------
# Backoff strategies
# ---------------------------------------------------------------------------


class TestConstantBackoff:
    def test_always_returns_same(self) -> None:
        b = ConstantBackoff(seconds=2.0)
        for i in range(5):
            assert b.delay(i) == 2.0


class TestLinearBackoff:
    def test_increases_linearly(self) -> None:
        b = LinearBackoff(initial=1.0, increment=0.5)
        assert b.delay(0) == 1.0
        assert b.delay(1) == 1.5
        assert b.delay(2) == 2.0

    def test_capped_at_max(self) -> None:
        b = LinearBackoff(initial=1.0, increment=1.0, max_seconds=2.5)
        assert b.delay(10) == 2.5


class TestExponentialBackoff:
    def test_doubles_each_attempt(self) -> None:
        b = ExponentialBackoff(base=1.0, multiplier=2.0)
        assert b.delay(0) == 1.0
        assert b.delay(1) == 2.0
        assert b.delay(2) == 4.0

    def test_capped_at_max(self) -> None:
        b = ExponentialBackoff(base=1.0, multiplier=2.0, max_seconds=5.0)
        assert b.delay(10) == 5.0


class TestNoJitter:
    def test_returns_base_unchanged(self) -> None:
        j = NoJitter()
        assert j.apply(3.0) == 3.0


class TestFullJitter:
    def test_within_range(self) -> None:
        j = FullJitter()
        for _ in range(20):
            v = j.apply(5.0)
            assert 0.0 <= v <= 5.0


# ---------------------------------------------------------------------------
# RetryPolicy — sync
# ---------------------------------------------------------------------------


class TestRetryPolicySync:
    def test_succeeds_on_first_try(self) -> None:
        calls = 0

        def op() -> str:
            nonlocal calls
            calls += 1
            return "ok"

        policy = RetryPolicy(max_attempts=3)
        result = policy.execute(op)
        assert result == "ok"
        assert calls == 1

    def test_retries_on_failure_then_succeeds(self) -> None:
        calls = 0

        def op() -> str:
            nonlocal calls
            calls += 1
            if calls < 3:
                raise ValueError("not yet")
            return "done"

        policy = RetryPolicy(
            max_attempts=3,
            backoff=ConstantBackoff(0),
            jitter=NoJitter(),
        )
        result = policy.execute(op)
        assert result == "done"
        assert calls == 3

    def test_exhausts_attempts_raises(self) -> None:
        def op() -> None:
            raise RuntimeError("always fails")

        policy = RetryPolicy(
            max_attempts=3,
            backoff=ConstantBackoff(0),
            jitter=NoJitter(),
        )
        with pytest.raises(RuntimeError, match="always fails"):
            policy.execute(op)

    def test_non_retryable_exception_propagates_immediately(self) -> None:
        calls = 0

        def op() -> None:
            nonlocal calls
            calls += 1
            raise TypeError("wrong type")

        policy = RetryPolicy(
            max_attempts=5,
            backoff=ConstantBackoff(0),
            jitter=NoJitter(),
            retryable_exceptions=(ValueError,),
        )
        with pytest.raises(TypeError):
            policy.execute(op)

        assert calls == 1  # no retries


# ---------------------------------------------------------------------------
# RetryPolicy — async
# ---------------------------------------------------------------------------


class TestRetryPolicyAsync:
    @pytest.mark.asyncio
    async def test_async_succeeds_immediately(self) -> None:
        async def op() -> int:
            return 99

        policy = RetryPolicy(max_attempts=3)
        result = await policy.execute_async(op)
        assert result == 99

    @pytest.mark.asyncio
    async def test_async_retries_and_succeeds(self) -> None:
        calls = 0

        async def op() -> str:
            nonlocal calls
            calls += 1
            if calls < 2:
                raise OSError("not ready")
            return "ready"

        policy = RetryPolicy(
            max_attempts=3,
            backoff=ConstantBackoff(0),
            jitter=NoJitter(),
        )
        result = await policy.execute_async(op)
        assert result == "ready"
        assert calls == 2

    @pytest.mark.asyncio
    async def test_async_exhausts_and_raises(self) -> None:
        async def op() -> None:
            raise ConnectionError("down")

        policy = RetryPolicy(
            max_attempts=2,
            backoff=ConstantBackoff(0),
            jitter=NoJitter(),
        )
        with pytest.raises(ConnectionError):
            await policy.execute_async(op)
