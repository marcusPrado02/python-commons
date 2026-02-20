"""OpenTelemetry adapter – OtelMetrics."""
from __future__ import annotations

from typing import Any

from mp_commons.observability.metrics import Counter, Gauge, Histogram, Metrics


def _require_otel() -> None:
    try:
        import opentelemetry  # noqa: F401
    except ImportError as exc:
        raise ImportError("Install 'mp-commons[otel]' to use the OpenTelemetry adapter") from exc


class _OtelCounter(Counter):
    def __init__(self, counter: Any) -> None:
        self._c = counter

    def add(self, value: float = 1.0, labels: dict[str, str] | None = None) -> None:
        self._c.add(value, attributes=labels)


class _OtelHistogram(Histogram):
    def __init__(self, hist: Any) -> None:
        self._h = hist

    def record(self, value: float, labels: dict[str, str] | None = None) -> None:
        self._h.record(value, attributes=labels)


class _OtelGauge(Gauge):
    def __init__(self) -> None:
        self._value = 0.0

    def set(self, value: float, labels: dict[str, str] | None = None) -> None:
        self._value = value

    def inc(self, labels: dict[str, str] | None = None) -> None:
        self._value += 1

    def dec(self, labels: dict[str, str] | None = None) -> None:
        self._value -= 1


class OtelMetrics(Metrics):
    """OpenTelemetry metrics adapter."""

    def __init__(self, meter_name: str = "mp_commons") -> None:
        _require_otel()
        from opentelemetry import metrics  # type: ignore[import-untyped]
        self._meter = metrics.get_meter(meter_name)

    def counter(self, name: str, description: str = "", unit: str = "") -> Counter:
        return _OtelCounter(self._meter.create_counter(name, description=description, unit=unit))

    def histogram(self, name: str, description: str = "", unit: str = "ms", boundaries: list[float] | None = None) -> Histogram:
        return _OtelHistogram(self._meter.create_histogram(name, description=description, unit=unit))

    def gauge(self, name: str, description: str = "", unit: str = "") -> Gauge:
        return _OtelGauge()


__all__ = ["OtelMetrics"]
