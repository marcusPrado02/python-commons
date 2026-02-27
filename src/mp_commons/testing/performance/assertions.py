"""Performance assertion helpers for unit and integration tests."""
from __future__ import annotations

import asyncio
import time
import tracemalloc
from typing import Any, Awaitable, Callable

__all__ = [
    "PerformanceAssertionError",
    "assert_completes_within",
    "assert_memory_increase_below",
    "assert_throughput",
]


class PerformanceAssertionError(AssertionError):
    """Raised when a performance assertion is violated."""


async def assert_completes_within(
    coro: Awaitable[Any], max_ms: float
) -> Any:
    """Run *coro* and assert it completes in at most *max_ms* milliseconds."""
    start = time.perf_counter()
    result = await coro
    elapsed_ms = (time.perf_counter() - start) * 1000
    if elapsed_ms > max_ms:
        raise PerformanceAssertionError(
            f"Coroutine took {elapsed_ms:.1f} ms, expected ≤ {max_ms} ms"
        )
    return result


async def assert_throughput(
    fn: Callable[[], Awaitable[Any]],
    min_ops_per_sec: float,
    duration_sec: float = 1.0,
) -> float:
    """Call *fn* repeatedly for *duration_sec* seconds; assert achieved ops/s ≥ *min_ops_per_sec*.

    Returns the actual achieved ops/sec.
    """
    deadline = time.perf_counter() + duration_sec
    ops = 0
    while time.perf_counter() < deadline:
        await fn()
        ops += 1
    actual_rps = ops / duration_sec
    if actual_rps < min_ops_per_sec:
        raise PerformanceAssertionError(
            f"Throughput {actual_rps:.1f} ops/s is below minimum {min_ops_per_sec} ops/s"
        )
    return actual_rps


def assert_memory_increase_below(
    fn: Callable[[], Any], max_bytes: int
) -> Any:
    """Call *fn* synchronously; assert memory growth < *max_bytes*.

    Returns the return value of *fn*.
    """
    tracemalloc.start()
    snapshot_before = tracemalloc.take_snapshot()
    result = fn()
    snapshot_after = tracemalloc.take_snapshot()
    tracemalloc.stop()

    stats = snapshot_after.compare_to(snapshot_before, "lineno")
    total_increase = sum(s.size_diff for s in stats if s.size_diff > 0)
    if total_increase > max_bytes:
        raise PerformanceAssertionError(
            f"Memory increased by {total_increase:,} bytes, expected < {max_bytes:,} bytes"
        )
    return result
