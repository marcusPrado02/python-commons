"""Testing fakes – FakeMetricsRegistry (§36.7)."""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from mp_commons.observability.metrics.ports import Counter, Gauge, Histogram, Metrics


class _FakeCounter(Counter):
    """In-memory counter that records all add() calls."""

    def __init__(self, name: str) -> None:
        self.name = name
        self._calls: list[tuple[float, dict[str, str] | None]] = []
        self.total: float = 0.0

    def add(self, value: float = 1.0, labels: dict[str, str] | None = None) -> None:
        self._calls.append((value, labels))
        self.total += value

    @property
    def call_count(self) -> int:
        return len(self._calls)


class _FakeHistogram(Histogram):
    """In-memory histogram that records all record() calls."""

    def __init__(self, name: str) -> None:
        self.name = name
        self._calls: list[tuple[float, dict[str, str] | None]] = []

    def record(self, value: float, labels: dict[str, str] | None = None) -> None:
        self._calls.append((value, labels))

    @property
    def call_count(self) -> int:
        return len(self._calls)

    @property
    def values(self) -> list[float]:
        return [v for v, _ in self._calls]


class _FakeGauge(Gauge):
    """In-memory gauge that records all set/inc/dec calls."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.current: float = 0.0
        self._calls: list[tuple[str, float | None, dict[str, str] | None]] = []

    def set(self, value: float, labels: dict[str, str] | None = None) -> None:
        self.current = value
        self._calls.append(("set", value, labels))

    def inc(self, labels: dict[str, str] | None = None) -> None:
        self.current += 1.0
        self._calls.append(("inc", None, labels))

    def dec(self, labels: dict[str, str] | None = None) -> None:
        self.current -= 1.0
        self._calls.append(("dec", None, labels))


class FakeMetricsRegistry(Metrics):
    """In-memory :class:`Metrics` double that records all instrument calls.

    Usage::

        metrics = FakeMetricsRegistry()
        counter = metrics.counter("requests_total")
        counter.add(1)
        metrics.assert_counter_incremented("requests_total", 1)
    """

    def __init__(self) -> None:
        self._counters: dict[str, _FakeCounter] = {}
        self._histograms: dict[str, _FakeHistogram] = {}
        self._gauges: dict[str, _FakeGauge] = {}

    # ------------------------------------------------------------------
    # Metrics protocol
    # ------------------------------------------------------------------

    def counter(self, name: str, description: str = "", unit: str = "") -> _FakeCounter:
        if name not in self._counters:
            self._counters[name] = _FakeCounter(name)
        return self._counters[name]

    def histogram(
        self,
        name: str,
        description: str = "",
        unit: str = "ms",
        boundaries: list[float] | None = None,
    ) -> _FakeHistogram:
        if name not in self._histograms:
            self._histograms[name] = _FakeHistogram(name)
        return self._histograms[name]

    def gauge(self, name: str, description: str = "", unit: str = "") -> _FakeGauge:
        if name not in self._gauges:
            self._gauges[name] = _FakeGauge(name)
        return self._gauges[name]

    # ------------------------------------------------------------------
    # Assertion helpers
    # ------------------------------------------------------------------

    def assert_counter_incremented(self, name: str, n: int = 1) -> None:
        """Assert that *name* counter was incremented exactly *n* times."""
        counter = self._counters.get(name)
        assert counter is not None, f"Counter '{name}' was never created"
        assert counter.call_count == n, (
            f"Counter '{name}' was incremented {counter.call_count} time(s), expected {n}"
        )

    def assert_counter_total(self, name: str, total: float) -> None:
        """Assert the cumulative total for *name* counter equals *total*."""
        counter = self._counters.get(name)
        assert counter is not None, f"Counter '{name}' was never created"
        assert counter.total == total, (
            f"Counter '{name}' total is {counter.total}, expected {total}"
        )

    def reset(self) -> None:
        """Clear all recorded metrics (useful between test cases)."""
        self._counters.clear()
        self._histograms.clear()
        self._gauges.clear()


__all__ = ["FakeMetricsRegistry"]
