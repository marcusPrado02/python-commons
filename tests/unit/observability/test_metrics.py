"""Unit tests for observability metrics (§21)."""

from __future__ import annotations

import dataclasses

import pytest

from mp_commons.observability.metrics import (
    BusinessMetric,
    Counter,
    Gauge,
    Histogram,
    MetricLabels,
    Metrics,
    NoopMetrics,
)


# ---------------------------------------------------------------------------
# Minimal stubs that implement the ABC ports
# ---------------------------------------------------------------------------


class _StubCounter(Counter):
    def __init__(self) -> None:
        self.calls: list[tuple[float, dict | None]] = []

    def add(self, value: float = 1.0, labels: dict[str, str] | None = None) -> None:
        self.calls.append((value, labels))


class _StubHistogram(Histogram):
    def __init__(self) -> None:
        self.calls: list[tuple[float, dict | None]] = []

    def record(self, value: float, labels: dict[str, str] | None = None) -> None:
        self.calls.append((value, labels))


class _StubGauge(Gauge):
    def __init__(self) -> None:
        self.value: float = 0.0
        self.inc_calls: int = 0
        self.dec_calls: int = 0

    def set(self, value: float, labels: dict[str, str] | None = None) -> None:
        self.value = value

    def inc(self, labels: dict[str, str] | None = None) -> None:
        self.inc_calls += 1
        self.value += 1

    def dec(self, labels: dict[str, str] | None = None) -> None:
        self.dec_calls += 1
        self.value -= 1


class _StubMetrics(Metrics):
    def counter(self, name: str, description: str = "", unit: str = "") -> Counter:
        return _StubCounter()

    def histogram(
        self,
        name: str,
        description: str = "",
        unit: str = "ms",
        boundaries: list[float] | None = None,
    ) -> Histogram:
        return _StubHistogram()

    def gauge(self, name: str, description: str = "", unit: str = "") -> Gauge:
        return _StubGauge()


# ---------------------------------------------------------------------------
# §21.1–21.3  Counter / Histogram / Gauge protocols
# ---------------------------------------------------------------------------


class TestCounterProtocol:
    def test_add_default_value(self) -> None:
        c = _StubCounter()
        c.add()
        assert c.calls == [(1.0, None)]

    def test_add_custom_value(self) -> None:
        c = _StubCounter()
        c.add(5.0, labels={"region": "us-east"})
        assert c.calls[0] == (5.0, {"region": "us-east"})

    def test_add_accumulates(self) -> None:
        c = _StubCounter()
        c.add(1.0)
        c.add(2.0)
        assert len(c.calls) == 2


class TestHistogramProtocol:
    def test_record_stores_value(self) -> None:
        h = _StubHistogram()
        h.record(42.5)
        assert h.calls == [(42.5, None)]

    def test_record_with_labels(self) -> None:
        h = _StubHistogram()
        h.record(10.0, labels={"method": "GET"})
        assert h.calls[0][1] == {"method": "GET"}

    def test_record_multiple(self) -> None:
        h = _StubHistogram()
        for v in (1.0, 2.0, 3.0):
            h.record(v)
        assert len(h.calls) == 3


class TestGaugeProtocol:
    def test_set_value(self) -> None:
        g = _StubGauge()
        g.set(99.0)
        assert g.value == 99.0

    def test_inc_increases(self) -> None:
        g = _StubGauge()
        g.inc()
        assert g.inc_calls == 1
        assert g.value == 1.0

    def test_dec_decreases(self) -> None:
        g = _StubGauge()
        g.set(5.0)
        g.dec()
        assert g.value == 4.0

    def test_inc_dec_balance(self) -> None:
        g = _StubGauge()
        for _ in range(3):
            g.inc()
        for _ in range(2):
            g.dec()
        assert g.value == 1.0


# ---------------------------------------------------------------------------
# §21.4  MetricsRegistry (stub)
# ---------------------------------------------------------------------------


class TestMetricsRegistryProtocol:
    def test_counter_returns_counter(self) -> None:
        m = _StubMetrics()
        c = m.counter("requests_total")
        assert isinstance(c, Counter)

    def test_histogram_returns_histogram(self) -> None:
        m = _StubMetrics()
        h = m.histogram("request_latency_ms")
        assert isinstance(h, Histogram)

    def test_gauge_returns_gauge(self) -> None:
        m = _StubMetrics()
        g = m.gauge("active_connections")
        assert isinstance(g, Gauge)

    def test_counter_with_description_and_unit(self) -> None:
        m = _StubMetrics()
        c = m.counter("hits", description="Cache hits", unit="1")
        assert isinstance(c, Counter)

    def test_histogram_with_boundaries(self) -> None:
        m = _StubMetrics()
        h = m.histogram("latency", boundaries=[5, 10, 50, 100, 500])
        assert isinstance(h, Histogram)


# ---------------------------------------------------------------------------
# §21.5  NoopMetrics
# ---------------------------------------------------------------------------


class TestNoopMetrics:
    def test_counter_does_not_raise(self) -> None:
        noop = NoopMetrics()
        c = noop.counter("x")
        c.add()
        c.add(3.0, labels={"env": "prod"})

    def test_histogram_does_not_raise(self) -> None:
        noop = NoopMetrics()
        h = noop.histogram("latency")
        h.record(1.5)
        h.record(0.0, labels={"route": "/health"})

    def test_gauge_does_not_raise(self) -> None:
        noop = NoopMetrics()
        g = noop.gauge("queue_depth")
        g.set(0.0)
        g.inc()
        g.dec()
        g.inc(labels={"queue": "default"})

    def test_noop_counter_returns_counter_instance(self) -> None:
        noop = NoopMetrics()
        assert isinstance(noop.counter("c"), Counter)

    def test_noop_histogram_returns_histogram_instance(self) -> None:
        noop = NoopMetrics()
        assert isinstance(noop.histogram("h"), Histogram)

    def test_noop_gauge_returns_gauge_instance(self) -> None:
        noop = NoopMetrics()
        assert isinstance(noop.gauge("g"), Gauge)

    def test_noop_is_metrics_instance(self) -> None:
        assert isinstance(NoopMetrics(), Metrics)


# ---------------------------------------------------------------------------
# §21.6 MetricLabels
# ---------------------------------------------------------------------------


class TestMetricLabels:
    def test_default_empty(self) -> None:
        ml = MetricLabels()
        assert ml.labels == {}

    def test_with_labels(self) -> None:
        ml = MetricLabels(labels={"env": "test"})
        assert ml.labels["env"] == "test"

    def test_is_frozen(self) -> None:
        ml = MetricLabels(labels={"k": "v"})
        with pytest.raises((dataclasses.FrozenInstanceError, TypeError)):
            ml.labels = {}  # type: ignore[misc]


# ---------------------------------------------------------------------------
# §21 BusinessMetric
# ---------------------------------------------------------------------------


class TestBusinessMetric:
    def test_record_calls_histogram(self) -> None:
        metric = BusinessMetric(
            name="order_total",
            description="Order total amount",
            unit="BRL",
        )
        m = _StubMetrics()
        # Replace histogram to track calls
        recorded: list[float] = []

        class _TrackingMetrics(_StubMetrics):
            def histogram(self, name: str, description: str = "", unit: str = "ms", boundaries: list[float] | None = None) -> Histogram:
                h = _StubHistogram()

                class _CapturingHistogram(_StubHistogram):
                    def record(self, value: float, labels: dict[str, str] | None = None) -> None:
                        recorded.append(value)

                return _CapturingHistogram()

        metric.record(_TrackingMetrics(), 99.90, customer_id="42")
        assert recorded == [99.90]

    def test_business_metric_attrs(self) -> None:
        m = BusinessMetric(name="n", description="d", unit="u", labels=("x",))
        assert m.name == "n"
        assert m.description == "d"
        assert m.unit == "u"
        assert m.labels == ("x",)
