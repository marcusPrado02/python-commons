"""Load test runner and report."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
import statistics
import time
from typing import Any

__all__ = [
    "LoadReport",
    "LoadTestError",
    "LoadTestRunner",
]


class LoadTestError(AssertionError):
    """Raised when a load test assertion is violated."""


@dataclass
class LoadReport:
    """Aggregated results from a load test run."""

    total_requests: int
    failures: int
    latencies_ms: list[float] = field(repr=False, default_factory=list)
    duration_sec: float = 0.0

    @property
    def success_count(self) -> int:
        return self.total_requests - self.failures

    @property
    def error_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.failures / self.total_requests

    @property
    def rps(self) -> float:
        if self.duration_sec <= 0:
            return 0.0
        return self.total_requests / self.duration_sec

    @property
    def p50_ms(self) -> float:
        return self._percentile(50)

    @property
    def p95_ms(self) -> float:
        return self._percentile(95)

    @property
    def p99_ms(self) -> float:
        return self._percentile(99)

    @property
    def max_ms(self) -> float:
        return max(self.latencies_ms, default=0.0)

    @property
    def min_ms(self) -> float:
        return min(self.latencies_ms, default=0.0)

    @property
    def mean_ms(self) -> float:
        if not self.latencies_ms:
            return 0.0
        return statistics.mean(self.latencies_ms)

    def _percentile(self, pct: int) -> float:
        if not self.latencies_ms:
            return 0.0
        sorted_lat = sorted(self.latencies_ms)
        idx = max(0, int(len(sorted_lat) * pct / 100) - 1)
        return sorted_lat[idx]

    def assert_p99_below(self, ms: float) -> None:
        """Assert that the 99th percentile latency is below *ms* milliseconds."""
        if self.p99_ms > ms:
            raise LoadTestError(f"p99 latency {self.p99_ms:.1f} ms exceeds threshold {ms} ms")

    def assert_error_rate_below(self, rate: float) -> None:
        """Assert that the error rate is below *rate* (0.0–1.0)."""
        if self.error_rate > rate:
            raise LoadTestError(f"error rate {self.error_rate:.2%} exceeds threshold {rate:.2%}")

    def assert_rps_above(self, min_rps: float) -> None:
        if self.rps < min_rps:
            raise LoadTestError(f"rps {self.rps:.1f} is below minimum {min_rps}")

    def summary(self) -> dict[str, Any]:
        return {
            "total_requests": self.total_requests,
            "failures": self.failures,
            "rps": round(self.rps, 2),
            "p50_ms": round(self.p50_ms, 2),
            "p95_ms": round(self.p95_ms, 2),
            "p99_ms": round(self.p99_ms, 2),
            "max_ms": round(self.max_ms, 2),
            "min_ms": round(self.min_ms, 2),
            "mean_ms": round(self.mean_ms, 2),
            "error_rate": round(self.error_rate, 4),
        }


class LoadTestRunner:
    """Simulate concurrent users running a scenario function for a fixed duration."""

    def __init__(self) -> None:
        self._latencies: list[float] = []
        self._failures: int = 0
        self._total: int = 0

    async def run(
        self,
        scenario_fn: Callable[[], Awaitable[Any]],
        users: int = 1,
        duration_sec: float = 1.0,
        ramp_up_sec: float = 0.0,
    ) -> LoadReport:
        """Run *scenario_fn* with *users* concurrent virtual users for *duration_sec*.

        Returns a ``LoadReport`` with collected metrics.
        """
        self._latencies = []
        self._failures = 0
        self._total = 0

        start_wall = time.perf_counter()
        deadline = start_wall + duration_sec

        async def _user_loop(ramp_delay: float) -> None:
            if ramp_delay > 0:
                await asyncio.sleep(ramp_delay)
            while time.perf_counter() < deadline:
                t0 = time.perf_counter()
                try:
                    await scenario_fn()
                except Exception:
                    self._failures += 1
                finally:
                    elapsed_ms = (time.perf_counter() - t0) * 1000
                    self._latencies.append(elapsed_ms)
                    self._total += 1

        ramp_step = ramp_up_sec / max(users, 1)
        tasks = [asyncio.create_task(_user_loop(i * ramp_step)) for i in range(users)]
        await asyncio.gather(*tasks, return_exceptions=True)

        actual_duration = time.perf_counter() - start_wall
        return LoadReport(
            total_requests=self._total,
            failures=self._failures,
            latencies_ms=list(self._latencies),
            duration_sec=actual_duration,
        )
