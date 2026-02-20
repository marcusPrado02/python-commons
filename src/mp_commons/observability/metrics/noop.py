"""Observability – NoopMetrics implementation."""
from __future__ import annotations

from mp_commons.observability.metrics.ports import Counter, Gauge, Histogram, Metrics


class _NoopCounter(Counter):
    def add(self, value: float = 1.0, labels: dict[str, str] | None = None) -> None:
        pass


class _NoopHistogram(Histogram):
    def record(self, value: float, labels: dict[str, str] | None = None) -> None:
        pass


class _NoopGauge(Gauge):
    def set(self, value: float, labels: dict[str, str] | None = None) -> None:
        pass

    def inc(self, labels: dict[str, str] | None = None) -> None:
        pass

    def dec(self, labels: dict[str, str] | None = None) -> None:
        pass


class NoopMetrics(Metrics):
    """Silent no-op metrics (useful in tests or when no backend is configured)."""

    def counter(self, name: str, description: str = "", unit: str = "") -> Counter:
        return _NoopCounter()

    def histogram(self, name: str, description: str = "", unit: str = "ms", boundaries: list[float] | None = None) -> Histogram:
        return _NoopHistogram()

    def gauge(self, name: str, description: str = "", unit: str = "") -> Gauge:
        return _NoopGauge()


__all__ = ["NoopMetrics"]
