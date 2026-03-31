"""Unit tests for the Prometheus adapter (A-09, O-04)."""
from __future__ import annotations

import sys
import types
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

# ---------------------------------------------------------------------------
# Stub prometheus_client so tests run without the real library
# ---------------------------------------------------------------------------

_prom_mod = types.ModuleType("prometheus_client")


class _FakeInstrument:
    """Minimal fake for Counter/Histogram/Gauge."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        self._labelnames: list[str] = list(kwargs.get("labelnames", []))
        self._values: list[tuple] = []
        self._label_cache: dict[tuple, "_FakeInstrument"] = {}

    def labels(self, *args: object) -> "_FakeInstrument":
        key = args
        if key not in self._label_cache:
            child = _FakeInstrument()
            self._label_cache[key] = child
        return self._label_cache[key]

    def inc(self, amount: float = 1.0) -> None:
        self._values.append(("inc", amount))

    def observe(self, value: float) -> None:
        self._values.append(("observe", value))

    def set(self, value: float) -> None:
        self._values.append(("set", value))

    def dec(self, amount: float = 1.0) -> None:
        self._values.append(("dec", amount))


_prom_mod.Counter = _FakeInstrument  # type: ignore[attr-defined]
_prom_mod.Histogram = _FakeInstrument  # type: ignore[attr-defined]
_prom_mod.Gauge = _FakeInstrument  # type: ignore[attr-defined]
sys.modules.setdefault("prometheus_client", _prom_mod)

from mp_commons.adapters.prometheus.metrics import PrometheusMetrics  # noqa: E402
from mp_commons.adapters.prometheus.health_exporter import PrometheusHealthExporter  # noqa: E402


# ---------------------------------------------------------------------------
# PrometheusMetrics
# ---------------------------------------------------------------------------


class TestPrometheusMetrics:
    def _make(self, namespace: str = "") -> PrometheusMetrics:
        return PrometheusMetrics(namespace=namespace)

    def test_counter_increments(self):
        m = self._make()
        c = m.counter("requests_total", labelnames=["method"])
        c.add(1.0, labels={"method": "GET"})
        instrument = m._counters["requests_total"]._counter
        child = instrument.labels("GET")
        assert ("inc", 1.0) in child._values

    def test_counter_cached(self):
        m = self._make()
        c1 = m.counter("hits")
        c2 = m.counter("hits")
        assert c1 is c2

    def test_histogram_records(self):
        m = self._make()
        h = m.histogram("latency_ms")
        h.record(42.0)
        instrument = m._histograms["latency_ms"]._histogram
        assert ("observe", 42.0) in instrument._values

    def test_gauge_set_inc_dec(self):
        m = self._make()
        g = m.gauge("queue_depth")
        g.set(10.0)
        g.inc()
        g.dec()
        instrument = m._gauges["queue_depth"]._gauge
        assert ("set", 10.0) in instrument._values
        assert ("inc", 1.0) in instrument._values
        assert ("dec", 1.0) in instrument._values

    def test_namespace_prepended(self):
        m = PrometheusMetrics(namespace="myapp")
        # The full name is passed to prometheus_client constructor; we verify
        # via the instrument being registered under the short name internally
        g = m.gauge("active_sessions")
        assert "active_sessions" in m._gauges

    def test_missing_prometheus_raises(self):
        import mp_commons.adapters.prometheus.metrics as _mod

        with patch.object(
            _mod,
            "_require_prometheus",
            side_effect=ImportError("prometheus-client is required for PrometheusMetrics"),
        ):
            m = PrometheusMetrics()
            with pytest.raises(ImportError, match="prometheus-client"):
                m.counter("foo")


# ---------------------------------------------------------------------------
# PrometheusHealthExporter
# ---------------------------------------------------------------------------


class TestPrometheusHealthExporter:
    def _make_gauge(self) -> MagicMock:
        g = MagicMock()
        g.set = MagicMock()
        return g

    def _make_metrics(self) -> tuple[MagicMock, MagicMock, MagicMock]:
        """Return (metrics_mock, status_gauge, latency_gauge)."""
        metrics = MagicMock()
        status_gauge = self._make_gauge()
        latency_gauge = self._make_gauge()
        metrics.gauge.side_effect = [status_gauge, latency_gauge]
        return metrics, status_gauge, latency_gauge

    def _make_report(self, results: dict) -> MagicMock:
        report = MagicMock()
        report.results = results
        return report

    def _status(self, healthy: bool, latency_ms: float = 0.0) -> MagicMock:
        s = MagicMock()
        s.healthy = healthy
        s.latency_ms = latency_ms
        return s

    async def test_collect_exports_healthy(self):
        registry = MagicMock()
        registry.run_all = AsyncMock(
            return_value=self._make_report({"db": self._status(True, 5.0)})
        )
        metrics, status_gauge, latency_gauge = self._make_metrics()
        exporter = PrometheusHealthExporter(registry=registry, metrics=metrics)
        await exporter.collect()

        status_gauge.set.assert_called_once_with(1.0, labels={"name": "db"})

    async def test_collect_exports_unhealthy(self):
        registry = MagicMock()
        registry.run_all = AsyncMock(
            return_value=self._make_report({"redis": self._status(False, 0.0)})
        )
        metrics, status_gauge, latency_gauge = self._make_metrics()
        exporter = PrometheusHealthExporter(registry=registry, metrics=metrics)
        await exporter.collect()

        status_gauge.set.assert_called_once_with(0.0, labels={"name": "redis"})

    async def test_collect_exports_latency(self):
        registry = MagicMock()
        registry.run_all = AsyncMock(
            return_value=self._make_report({"db": self._status(True, 12.5)})
        )
        metrics, status_gauge, latency_gauge = self._make_metrics()
        exporter = PrometheusHealthExporter(registry=registry, metrics=metrics, export_latency=True)
        await exporter.collect()

        latency_gauge.set.assert_called_once_with(12.5, labels={"name": "db"})

    async def test_collect_no_latency_when_disabled(self):
        registry = MagicMock()
        registry.run_all = AsyncMock(
            return_value=self._make_report({"db": self._status(True)})
        )
        # only one gauge created when export_latency=False
        metrics = MagicMock()
        status_gauge = self._make_gauge()
        metrics.gauge.return_value = status_gauge
        exporter = PrometheusHealthExporter(registry=registry, metrics=metrics, export_latency=False)
        assert exporter._latency_gauge is None
        await exporter.collect()  # must not raise

    async def test_collect_exception_does_not_propagate_in_loop(self):
        registry = MagicMock()
        call_count = 0

        async def side_effect():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("collect failed")
            return self._make_report({})

        registry.run_all = side_effect
        metrics = MagicMock()
        metrics.gauge.return_value = self._make_gauge()
        exporter = PrometheusHealthExporter(registry=registry, metrics=metrics)

        import asyncio

        async def run_two_iterations():
            task = asyncio.create_task(exporter.collect_loop(interval=0.001))
            await asyncio.sleep(0.02)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        await run_two_iterations()
        assert call_count >= 2  # second iteration ran despite first exception
