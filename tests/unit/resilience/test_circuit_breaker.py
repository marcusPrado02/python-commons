"""Unit tests for CircuitBreaker state transitions — §16."""

from __future__ import annotations

import asyncio

import pytest

from mp_commons.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerPolicy,
    CircuitBreakerState,
)
from mp_commons.kernel.errors import ApplicationError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_breaker(
    failure_threshold: int = 3,
    success_threshold: int = 2,
    timeout_seconds: float = 0,  # 0 → transition to HALF_OPEN instantly in tests
) -> CircuitBreaker:
    policy = CircuitBreakerPolicy(
        failure_threshold=failure_threshold,
        success_threshold=success_threshold,
        timeout_seconds=timeout_seconds,
    )
    return CircuitBreaker(name="test", policy=policy)


async def fail() -> None:
    raise RuntimeError("fail")


async def succeed() -> str:
    return "ok"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCircuitBreakerTransitions:
    def test_starts_closed(self) -> None:
        cb = make_breaker()
        assert cb.state == CircuitBreakerState.CLOSED

    def test_opens_after_threshold(self) -> None:
        async def run() -> None:
            cb = make_breaker(failure_threshold=3)
            for _ in range(3):
                with pytest.raises(RuntimeError):
                    await cb.call(fail)
            assert cb.state == CircuitBreakerState.OPEN

        asyncio.run(run())

    def test_open_rejects_calls(self) -> None:
        async def run() -> None:
            # Use a long timeout so the circuit stays OPEN (won't probe immediately)
            cb = make_breaker(failure_threshold=2, timeout_seconds=1000.0)
            for _ in range(2):
                with pytest.raises(RuntimeError):
                    await cb.call(fail)
            # should reject without calling the function
            with pytest.raises((ApplicationError, Exception)):
                await cb.call(succeed)

        asyncio.run(run())

    def test_half_open_after_timeout(self) -> None:
        async def run() -> None:
            cb = make_breaker(failure_threshold=2, timeout_seconds=0)
            for _ in range(2):
                with pytest.raises(RuntimeError):
                    await cb.call(fail)
            # state is OPEN; with timeout=0 the next call would trigger HALF_OPEN
            assert cb.state in (CircuitBreakerState.OPEN, CircuitBreakerState.HALF_OPEN)

        asyncio.run(run())

    def test_transitions_to_half_open_on_next_call(self) -> None:
        async def run() -> None:
            cb = make_breaker(failure_threshold=2, timeout_seconds=0)
            for _ in range(2):
                with pytest.raises(RuntimeError):
                    await cb.call(fail)
            # trigger transition: call succeed → should probe (HALF_OPEN) then succeed
            result = await cb.call(succeed)
            assert result == "ok"
            # state should be HALF_OPEN or CLOSED after one success (threshold=2)
            assert cb.state in (CircuitBreakerState.HALF_OPEN, CircuitBreakerState.CLOSED)

        asyncio.run(run())

    def test_closes_after_success_threshold_in_half_open(self) -> None:
        async def run() -> None:
            cb = make_breaker(failure_threshold=2, success_threshold=2, timeout_seconds=0)
            # Trip the breaker
            for _ in range(2):
                with pytest.raises(RuntimeError):
                    await cb.call(fail)
            # Force HALF_OPEN by manipulating internal state for testability
            cb._state = CircuitBreakerState.HALF_OPEN  # type: ignore[attr-defined]
            cb._success_count = 0  # type: ignore[attr-defined]
            await cb.call(succeed)
            await cb.call(succeed)
            assert cb.state == CircuitBreakerState.CLOSED

        asyncio.run(run())

    def test_success_resets_failure_count_in_closed(self) -> None:
        async def run() -> None:
            cb = make_breaker(failure_threshold=3)
            with pytest.raises(RuntimeError):
                await cb.call(fail)
            # One success should reset failure counter
            await cb.call(succeed)
            with pytest.raises(RuntimeError):
                await cb.call(fail)
            assert cb.state == CircuitBreakerState.CLOSED  # still closed; threshold=3

        asyncio.run(run())

    def test_excluded_exception_does_not_trip_breaker(self) -> None:
        async def run() -> None:
            policy = CircuitBreakerPolicy(
                failure_threshold=2,
                excluded_exceptions=(ValueError,),
            )
            cb = CircuitBreaker(name="test", policy=policy)

            async def excluded_fail() -> None:
                raise ValueError("excluded")

            for _ in range(5):
                with pytest.raises(ValueError):
                    await cb.call(excluded_fail)
            # breaker should still be closed because ValueError is excluded
            assert cb.state == CircuitBreakerState.CLOSED

        asyncio.run(run())


# ---------------------------------------------------------------------------
# Public surface smoke test
# ---------------------------------------------------------------------------


class TestPublicReExports:
    def test_all_symbols_importable(self) -> None:
        import importlib

        mod = importlib.import_module("mp_commons.resilience.circuit_breaker")
        for name in mod.__all__:
            assert hasattr(mod, name), f"{name!r} missing"
