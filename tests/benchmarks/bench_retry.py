"""§47.3 — Benchmark: RetryPolicy.execute_async overhead.

Compares:
- Bare ``await fn()`` (baseline — no retry wrapper)
- ``RetryPolicy(max_attempts=1).execute_async(fn)`` — single attempt, zero retries
- ``RetryPolicy(max_attempts=3).execute_async(fn)`` — three attempts configured,
  but succeeds on first try (no actual retries)

Goal: quantify the bookkeeping overhead of the retry wrapper itself.
"""

from __future__ import annotations

import asyncio

import pytest

from mp_commons.resilience.retry import RetryPolicy


# ---------------------------------------------------------------------------
# Shared coroutine factories
# ---------------------------------------------------------------------------


async def _noop() -> str:
    """Cheapest possible coroutine — simulates an already-cached hot path."""
    return "ok"


# ---------------------------------------------------------------------------
# Benchmarks
# ---------------------------------------------------------------------------


def test_bare_await_baseline(benchmark, event_loop):
    """Raw ``await _noop()`` — establishes the event-loop call floor."""

    def run():
        return event_loop.run_until_complete(_noop())

    result = benchmark(run)
    assert result == "ok"


def test_retry_policy_max_1(benchmark, event_loop):
    """RetryPolicy(max_attempts=1) — no retry logic executes at all."""
    policy = RetryPolicy(max_attempts=1)

    def run():
        return event_loop.run_until_complete(policy.execute_async(_noop))

    result = benchmark(run)
    assert result == "ok"


def test_retry_policy_max_3_no_retries(benchmark, event_loop):
    """RetryPolicy(max_attempts=3) — succeeds immediately; no sleeps."""
    policy = RetryPolicy(max_attempts=3)

    def run():
        return event_loop.run_until_complete(policy.execute_async(_noop))

    result = benchmark(run)
    assert result == "ok"


def test_retry_policy_max_5_no_retries(benchmark, event_loop):
    """RetryPolicy(max_attempts=5) — checks overhead of deeper attempt budget."""
    policy = RetryPolicy(max_attempts=5)

    def run():
        return event_loop.run_until_complete(policy.execute_async(_noop))

    result = benchmark(run)
    assert result == "ok"


def test_retry_policy_reuse_instance(benchmark, event_loop):
    """Re-use a single RetryPolicy instance across calls (typical production use)."""
    policy = RetryPolicy(max_attempts=3)
    call_count = [0]

    async def counter() -> int:
        call_count[0] += 1
        return call_count[0]

    def run():
        return event_loop.run_until_complete(policy.execute_async(counter))

    benchmark(run)
    assert call_count[0] > 0
