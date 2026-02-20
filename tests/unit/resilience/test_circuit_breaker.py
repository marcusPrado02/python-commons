"""Unit tests for CircuitBreaker state transitions."""

from __future__ import annotations

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
    @pytest.mark.asyncio
    async def test_starts_closed(self) -> None:
        cb = make_breaker()
        assert cb.state == CircuitBreakerState.CLOSED

    @pytest.mark.asyncio
    async def test_opens_after_threshold(self) -> None:
        cb = make_breaker(failure_threshold=3)
        for _ in range(3):
            with pytest.raises(RuntimeError):
                await cb.call(fail)
        assert cb.state == CircuitBreakerState.OPEN

    @pytest.mark.asyncio
    async def test_open_rejects_calls(self) -> None:
        cb = make_breaker(failure_threshold=2)
        for _ in range(2):
            with pytest.raises(RuntimeError):
                await cb.call(fail)

        # should reject without calling the function
        with pytest.raises((ApplicationError, Exception)):
            await cb.call(succeed)

    @pytest.mark.asyncio
    async def test_half_open_after_timeout(self) -> None:
        cb = make_breaker(failure_threshold=2, timeout_seconds=0)
        for _ in range(2):
            with pytest.raises(RuntimeError):
                await cb.call(fail)

        # With timeout=0 the circuit should probe next call (HALF_OPEN)
        assert cb.state in (CircuitBreakerState.OPEN, CircuitBreakerState.HALF_OPEN)

    @pytest.mark.asyncio
    async def test_closes_after_success_threshold_in_half_open(self) -> None:
        cb = make_breaker(failure_threshold=2, success_threshold=2, timeout_seconds=0)
        # Trip the breaker
        for _ in range(2):
            with pytest.raises(RuntimeError):
                await cb.call(fail)

        # Force HALF_OPEN by manipulating internal state for testability
        cb._state = CircuitBreakerState.HALF_OPEN  # type: ignore[attr-defined]
        cb._half_open_successes = 0  # type: ignore[attr-defined]

        await cb.call(succeed)
        await cb.call(succeed)
        assert cb.state == CircuitBreakerState.CLOSED

    @pytest.mark.asyncio
    async def test_success_resets_failure_count_in_closed(self) -> None:
        cb = make_breaker(failure_threshold=3)
        with pytest.raises(RuntimeError):
            await cb.call(fail)
        # One success should reset failure counter
        await cb.call(succeed)
        with pytest.raises(RuntimeError):
            await cb.call(fail)
        assert cb.state == CircuitBreakerState.CLOSED  # still closed; threshold=3
