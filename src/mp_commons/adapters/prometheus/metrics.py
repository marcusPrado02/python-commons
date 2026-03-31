"""Prometheus implementation of the ``Metrics`` port.

Implements :class:`~mp_commons.observability.metrics.Metrics` backed by
``prometheus_client`` so metric instruments can be dropped into any existing
code that depends only on the abstract port.

Usage::

    from mp_commons.adapters.prometheus import PrometheusMetrics

    metrics = PrometheusMetrics(namespace="myapp")
    requests = metrics.counter("http_requests_total", description="Total HTTP requests")
    requests.add(1, labels={"method": "GET", "status": "200"})

The adapter creates ``prometheus_client`` instruments lazily on first access and
caches them by name so repeated calls to ``counter("foo")`` always return the
same underlying instrument.
"""
from __future__ import annotations

from typing import Any


def _require_prometheus() -> Any:
    try:
        import prometheus_client  # type: ignore[import-untyped]

        return prometheus_client
    except ImportError as exc:
        raise ImportError(
            "prometheus-client is required for PrometheusMetrics. "
            "Install it with: pip install 'prometheus-client>=0.20'"
        ) from exc


class _PrometheusCounter:
    def __init__(self, counter: Any) -> None:
        self._counter = counter

    def add(self, value: float = 1.0, labels: dict[str, str] | None = None) -> None:
        if labels:
            label_values = [labels.get(k, "") for k in sorted(labels)]
            self._counter.labels(*label_values).inc(value)
        else:
            self._counter.inc(value)


class _PrometheusHistogram:
    def __init__(self, histogram: Any) -> None:
        self._histogram = histogram

    def record(self, value: float, labels: dict[str, str] | None = None) -> None:
        if labels:
            label_values = [labels.get(k, "") for k in sorted(labels)]
            self._histogram.labels(*label_values).observe(value)
        else:
            self._histogram.observe(value)


class _PrometheusGauge:
    def __init__(self, gauge: Any) -> None:
        self._gauge = gauge

    def set(self, value: float, labels: dict[str, str] | None = None) -> None:
        if labels:
            label_values = [labels.get(k, "") for k in sorted(labels)]
            self._gauge.labels(*label_values).set(value)
        else:
            self._gauge.set(value)

    def inc(self, labels: dict[str, str] | None = None) -> None:
        if labels:
            label_values = [labels.get(k, "") for k in sorted(labels)]
            self._gauge.labels(*label_values).inc()
        else:
            self._gauge.inc()

    def dec(self, labels: dict[str, str] | None = None) -> None:
        if labels:
            label_values = [labels.get(k, "") for k in sorted(labels)]
            self._gauge.labels(*label_values).dec()
        else:
            self._gauge.dec()


class PrometheusMetrics:
    """``prometheus_client``-backed implementation of the ``Metrics`` port.

    Parameters
    ----------
    namespace:
        String prepended to every metric name with an underscore separator.
        Example: ``namespace="myapp"`` → metric ``"http_requests_total"``
        becomes ``"myapp_http_requests_total"``.
    registry:
        Custom ``prometheus_client.CollectorRegistry``.  Defaults to the
        global ``REGISTRY``.  Pass a fresh ``CollectorRegistry()`` in tests
        to avoid cross-test pollution.

    Usage::

        metrics = PrometheusMetrics(namespace="api")
        latency = metrics.histogram("request_duration_seconds")
        latency.record(0.042, labels={"route": "/users"})
    """

    def __init__(
        self,
        namespace: str = "",
        registry: Any = None,
    ) -> None:
        self._namespace = namespace
        self._registry = registry  # None → prometheus_client default registry
        self._counters: dict[str, _PrometheusCounter] = {}
        self._histograms: dict[str, _PrometheusHistogram] = {}
        self._gauges: dict[str, _PrometheusGauge] = {}

    def _full_name(self, name: str) -> str:
        return f"{self._namespace}_{name}" if self._namespace else name

    def counter(
        self,
        name: str,
        description: str = "",
        unit: str = "",
        labelnames: list[str] | None = None,
    ) -> _PrometheusCounter:
        """Return (or create) a Prometheus Counter instrument."""
        if name not in self._counters:
            pc = _require_prometheus()
            kwargs: dict[str, Any] = {}
            if self._registry is not None:
                kwargs["registry"] = self._registry
            if labelnames:
                kwargs["labelnames"] = sorted(labelnames)
            instrument = pc.Counter(
                self._full_name(name),
                description or name,
                **kwargs,
            )
            self._counters[name] = _PrometheusCounter(instrument)
        return self._counters[name]

    def histogram(
        self,
        name: str,
        description: str = "",
        unit: str = "ms",
        boundaries: list[float] | None = None,
        labelnames: list[str] | None = None,
    ) -> _PrometheusHistogram:
        """Return (or create) a Prometheus Histogram instrument."""
        if name not in self._histograms:
            pc = _require_prometheus()
            kwargs: dict[str, Any] = {}
            if self._registry is not None:
                kwargs["registry"] = self._registry
            if boundaries:
                kwargs["buckets"] = boundaries
            if labelnames:
                kwargs["labelnames"] = sorted(labelnames)
            instrument = pc.Histogram(
                self._full_name(name),
                description or name,
                **kwargs,
            )
            self._histograms[name] = _PrometheusHistogram(instrument)
        return self._histograms[name]

    def gauge(
        self,
        name: str,
        description: str = "",
        unit: str = "",
        labelnames: list[str] | None = None,
    ) -> _PrometheusGauge:
        """Return (or create) a Prometheus Gauge instrument."""
        if name not in self._gauges:
            pc = _require_prometheus()
            kwargs: dict[str, Any] = {}
            if self._registry is not None:
                kwargs["registry"] = self._registry
            if labelnames:
                kwargs["labelnames"] = sorted(labelnames)
            instrument = pc.Gauge(
                self._full_name(name),
                description or name,
                **kwargs,
            )
            self._gauges[name] = _PrometheusGauge(instrument)
        return self._gauges[name]


__all__ = ["PrometheusMetrics"]
