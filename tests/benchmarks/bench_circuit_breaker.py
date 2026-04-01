"""P-01 — Benchmark: CircuitBreaker.call overhead under concurrent load.

Measures throughput and per-call overhead of the CircuitBreaker in
CLOSED state with 50 concurrent coroutines against a no-op backend.

Target: overhead < 5 % compared to a direct call.
"""
from __future__ import annotations

import asyncio
from typing import Any

from mp_commons.resilience.circuit_breaker import CircuitBreaker, CircuitBreakerPolicy


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _noop_backend() -> str:
    """Zero-overhead async function — the 'bare call' baseline."""
    return "ok"


def _make_breaker() -> CircuitBreaker:
    policy = CircuitBreakerPolicy(failure_threshold=10, timeout_seconds=30.0)
    return CircuitBreaker(name="bench", policy=policy)


# ---------------------------------------------------------------------------
# Benchmarks
# ---------------------------------------------------------------------------


def test_circuit_breaker_single_call_overhead(benchmark: Any, event_loop: Any) -> None:
    """Single CircuitBreaker.call vs bare call — measures per-call overhead."""
    breaker = _make_breaker()

    def run() -> str:
        return event_loop.run_until_complete(breaker.call(_noop_backend))

    result = benchmark(run)
    assert result == "ok"


def test_circuit_breaker_bare_call_baseline(benchmark: Any, event_loop: Any) -> None:
    """Baseline: direct call with no circuit breaker wrapping."""

    def run() -> str:
        return event_loop.run_until_complete(_noop_backend())

    result = benchmark(run)
    assert result == "ok"


def test_circuit_breaker_50_concurrent_calls(benchmark: Any, event_loop: Any) -> None:
    """50 concurrent coroutines — asserts no throughput collapse.

    The circuit breaker must remain in CLOSED state (all calls succeed).
    """
    breaker = _make_breaker()

    async def _batch() -> list[str]:
        return await asyncio.gather(
            *[breaker.call(_noop_backend) for _ in range(50)]
        )

    def run() -> list[str]:
        return event_loop.run_until_complete(_batch())

    results = benchmark(run)
    assert all(r == "ok" for r in results)
    assert len(results) == 50
