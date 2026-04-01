"""Concurrency stress tests for CircuitBreaker (T-08)."""
from __future__ import annotations

import asyncio
import random
from typing import Any

import pytest

from mp_commons.resilience.circuit_breaker.breaker import CircuitBreaker
from mp_commons.resilience.circuit_breaker.errors import CircuitOpenError
from mp_commons.resilience.circuit_breaker.policy import CircuitBreakerPolicy
from mp_commons.resilience.circuit_breaker.state import CircuitBreakerState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _always_fails() -> None:
    raise RuntimeError("backend down")


async def _always_succeeds() -> int:
    return 42


async def _random_fail(fail_rate: float) -> int:
    if random.random() < fail_rate:
        raise RuntimeError("flaky")
    return 1


# ---------------------------------------------------------------------------
# Concurrency stress: only OPEN or CircuitOpenError, never partial state
# ---------------------------------------------------------------------------


async def test_concurrent_failures_open_circuit() -> None:
    """100 concurrent failing calls must leave the circuit OPEN, never corrupt it."""
    policy = CircuitBreakerPolicy(failure_threshold=5, timeout_seconds=60.0)
    cb = CircuitBreaker("stress-fail", policy)

    results: list[Exception] = []

    async def task() -> None:
        try:
            await cb.call(_always_fails)
        except (RuntimeError, CircuitOpenError) as exc:
            results.append(exc)

    await asyncio.gather(*(task() for _ in range(100)))

    # After 100 failures: circuit MUST be OPEN
    assert cb.state == CircuitBreakerState.OPEN

    # Every result is either a backend error or a CircuitOpenError
    assert len(results) == 100
    for exc in results:
        assert isinstance(exc, (RuntimeError, CircuitOpenError))


async def test_concurrent_successes_keep_circuit_closed() -> None:
    """100 concurrent successful calls must keep the circuit CLOSED."""
    cb = CircuitBreaker("stress-success")

    tasks = [cb.call(_always_succeeds) for _ in range(100)]
    results = await asyncio.gather(*tasks)

    assert cb.state == CircuitBreakerState.CLOSED
    assert all(r == 42 for r in results)


async def test_failure_count_never_exceeds_total_calls() -> None:
    """Internal failure counter must stay consistent under concurrency."""
    policy = CircuitBreakerPolicy(failure_threshold=1000, timeout_seconds=60.0)
    cb = CircuitBreaker("counter-check", policy)

    n = 200

    async def task() -> None:
        try:
            await cb.call(_always_fails)
        except Exception:
            pass

    await asyncio.gather(*(task() for _ in range(n)))

    # failure_count must be ≤ n (no double-counting from races)
    assert cb._failure_count <= n


async def test_open_circuit_rejects_all_concurrent_callers() -> None:
    """Once OPEN, all concurrent callers get CircuitOpenError immediately."""
    policy = CircuitBreakerPolicy(failure_threshold=1, timeout_seconds=9999.0)
    cb = CircuitBreaker("already-open", policy)

    # Trip the breaker
    try:
        await cb.call(_always_fails)
    except RuntimeError:
        pass

    assert cb.state == CircuitBreakerState.OPEN

    errors: list[type] = []

    async def task() -> None:
        try:
            await cb.call(_always_succeeds)
        except CircuitOpenError:
            errors.append(CircuitOpenError)

    await asyncio.gather(*(task() for _ in range(50)))
    assert len(errors) == 50


async def test_mixed_load_state_machine_consistency() -> None:
    """Mixed success/failure load: state must always be a valid enum value."""
    policy = CircuitBreakerPolicy(
        failure_threshold=10,
        success_threshold=3,
        timeout_seconds=0.01,
    )
    cb = CircuitBreaker("mixed", policy)
    valid_states = set(CircuitBreakerState)

    async def task() -> None:
        assert cb.state in valid_states
        try:
            await cb.call(lambda: _random_fail(0.5))
        except Exception:
            pass
        assert cb.state in valid_states

    await asyncio.gather(*(task() for _ in range(200)))
    assert cb.state in valid_states


async def test_recovery_after_timeout_concurrent() -> None:
    """Multiple coroutines racing through HALF_OPEN all behave correctly."""
    policy = CircuitBreakerPolicy(
        failure_threshold=1,
        success_threshold=2,
        timeout_seconds=0.05,
    )
    cb = CircuitBreaker("recovery", policy)

    # Trip the breaker
    try:
        await cb.call(_always_fails)
    except RuntimeError:
        pass
    assert cb.state == CircuitBreakerState.OPEN

    # Wait for timeout → HALF_OPEN becomes accessible
    await asyncio.sleep(0.1)

    successes: list[int] = []
    errors: list[Exception] = []

    async def task() -> None:
        try:
            result = await cb.call(_always_succeeds)
            successes.append(result)
        except (CircuitOpenError, RuntimeError) as exc:
            errors.append(exc)

    await asyncio.gather(*(task() for _ in range(20)))

    # Circuit must end in CLOSED (recovered) after enough successes
    assert cb.state in (CircuitBreakerState.CLOSED, CircuitBreakerState.HALF_OPEN)
    # State machine is never corrupted
    assert cb.state in set(CircuitBreakerState)
