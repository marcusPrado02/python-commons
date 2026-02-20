"""Unit tests for RetryPolicy and backoff/jitter strategies — §15."""

from __future__ import annotations

import asyncio

import pytest

from mp_commons.resilience.retry import (
    ConstantBackoff,
    EqualJitter,
    ExponentialBackoff,
    FullJitter,
    LinearBackoff,
    NoJitter,
    RetryPolicy,
)


# ---------------------------------------------------------------------------
# BackoffStrategy — ConstantBackoff (15.2)
# ---------------------------------------------------------------------------


class TestConstantBackoff:
    def test_always_returns_same(self) -> None:
        b = ConstantBackoff(delay=2.0)
        for i in range(5):
            assert b.compute(i) == 2.0

    def test_default_delay(self) -> None:
        b = ConstantBackoff()
        assert b.compute(0) == 1.0

    def test_zero_delay(self) -> None:
        b = ConstantBackoff(delay=0.0)
        assert b.compute(99) == 0.0


# ---------------------------------------------------------------------------
# BackoffStrategy — LinearBackoff
# ---------------------------------------------------------------------------


class TestLinearBackoff:
    def test_grows_with_attempt(self) -> None:
        b = LinearBackoff(base_delay=1.0)
        assert b.compute(0) == 0.0
        assert b.compute(1) == 1.0
        assert b.compute(2) == 2.0

    def test_capped_at_max(self) -> None:
        b = LinearBackoff(base_delay=1.0, max_delay=2.5)
        assert b.compute(10) == 2.5

    def test_default_max_delay(self) -> None:
        b = LinearBackoff(base_delay=1.0)
        assert b.compute(1000) == 30.0


# ---------------------------------------------------------------------------
# BackoffStrategy — ExponentialBackoff (15.3)
# ---------------------------------------------------------------------------


class TestExponentialBackoff:
    def test_doubles_each_attempt(self) -> None:
        b = ExponentialBackoff(base_delay=1.0)
        assert b.compute(0) == 1.0
        assert b.compute(1) == 2.0
        assert b.compute(2) == 4.0

    def test_capped_at_max(self) -> None:
        b = ExponentialBackoff(base_delay=1.0, max_delay=5.0)
        assert b.compute(10) == 5.0

    def test_default_values(self) -> None:
        b = ExponentialBackoff()
        assert b.compute(0) == 0.1
        assert b.compute(1) == 0.2


# ---------------------------------------------------------------------------
# JitterStrategy (15.4)
# ---------------------------------------------------------------------------


class TestNoJitter:
    def test_returns_base_unchanged(self) -> None:
        j = NoJitter()
        assert j.apply(3.0) == 3.0

    def test_zero_unchanged(self) -> None:
        j = NoJitter()
        assert j.apply(0.0) == 0.0


class TestFullJitter:
    def test_within_range(self) -> None:
        j = FullJitter()
        for _ in range(50):
            v = j.apply(5.0)
            assert 0.0 <= v <= 5.0

    def test_zero_base_returns_zero(self) -> None:
        j = FullJitter()
        assert j.apply(0.0) == 0.0


class TestEqualJitter:
    def test_within_range(self) -> None:
        j = EqualJitter()
        for _ in range(50):
            v = j.apply(4.0)
            assert 2.0 <= v <= 4.0

    def test_zero_base_returns_zero(self) -> None:
        j = EqualJitter()
        assert j.apply(0.0) == 0.0


# ---------------------------------------------------------------------------
# RetryPolicy — sync (15.5)
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

    def test_max_attempts_one_no_retry(self) -> None:
        calls = 0

        def op() -> None:
            nonlocal calls
            calls += 1
            raise OSError("fail")

        policy = RetryPolicy(
            max_attempts=1,
            backoff=ConstantBackoff(0),
            jitter=NoJitter(),
        )
        with pytest.raises(OSError):
            policy.execute(op)

        assert calls == 1


# ---------------------------------------------------------------------------
# RetryPolicy — async (15.5)
# ---------------------------------------------------------------------------


class TestRetryPolicyAsync:
    def test_async_succeeds_immediately(self) -> None:
        async def op() -> int:
            return 99

        async def run() -> int:
            policy = RetryPolicy(max_attempts=3)
            return await policy.execute_async(op)

        assert asyncio.run(run()) == 99

    def test_async_retries_and_succeeds(self) -> None:
        calls = 0

        async def op() -> str:
            nonlocal calls
            calls += 1
            if calls < 2:
                raise OSError("not ready")
            return "ready"

        async def run() -> str:
            policy = RetryPolicy(
                max_attempts=3,
                backoff=ConstantBackoff(0),
                jitter=NoJitter(),
            )
            return await policy.execute_async(op)

        result = asyncio.run(run())
        assert result == "ready"
        assert calls == 2

    def test_async_exhausts_and_raises(self) -> None:
        async def op() -> None:
            raise ConnectionError("down")

        async def run() -> None:
            policy = RetryPolicy(
                max_attempts=2,
                backoff=ConstantBackoff(0),
                jitter=NoJitter(),
            )
            await policy.execute_async(op)

        with pytest.raises(ConnectionError):
            asyncio.run(run())

    def test_async_non_retryable_propagates_immediately(self) -> None:
        calls = 0

        async def op() -> None:
            nonlocal calls
            calls += 1
            raise KeyError("key")

        async def run() -> None:
            policy = RetryPolicy(
                max_attempts=5,
                backoff=ConstantBackoff(0),
                jitter=NoJitter(),
                retryable_exceptions=(ValueError,),
            )
            await policy.execute_async(op)

        with pytest.raises(KeyError):
            asyncio.run(run())

        assert calls == 1


# ---------------------------------------------------------------------------
# Public surface smoke test
# ---------------------------------------------------------------------------


class TestPublicReExports:
    def test_all_symbols_importable(self) -> None:
        import importlib

        mod = importlib.import_module("mp_commons.resilience.retry")
        for name in mod.__all__:
            assert hasattr(mod, name), f"{name!r} missing"
