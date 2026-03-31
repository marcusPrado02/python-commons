"""Prometheus health exporter (O-04).

Runs a :class:`~mp_commons.observability.health.HealthRegistry` and exposes
each check's result as a Prometheus Gauge metric::

    mp_commons_health_check{name="database"} 1.0
    mp_commons_health_check{name="redis"} 0.0

Optionally also exports the latency of each check::

    mp_commons_health_check_latency_ms{name="database"} 3.14

Usage::

    exporter = PrometheusHealthExporter(
        registry=health_registry,
        metrics=PrometheusMetrics(namespace="myapp"),
    )
    await exporter.collect()   # run checks and update metrics

    # Or integrate with a FastAPI background task / scheduler:
    @app.on_event("startup")
    async def start_health_collector():
        asyncio.create_task(exporter.collect_loop(interval=15.0))
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

_GAUGE_NAME = "health_check"
_LATENCY_GAUGE_NAME = "health_check_latency_ms"


class PrometheusHealthExporter:
    """Export :class:`~mp_commons.observability.health.HealthRegistry` results
    as Prometheus Gauge metrics.

    Parameters
    ----------
    registry:
        A :class:`~mp_commons.observability.health.HealthRegistry` instance.
    metrics:
        A :class:`~mp_commons.adapters.prometheus.PrometheusMetrics` instance
        (or any object implementing ``gauge(name, …)``).
    export_latency:
        When ``True`` (default), also exports a ``health_check_latency_ms``
        gauge for each check.
    """

    def __init__(
        self,
        registry: Any,
        metrics: Any,
        *,
        export_latency: bool = True,
    ) -> None:
        self._registry = registry
        self._metrics = metrics
        self._export_latency = export_latency
        self._gauge = metrics.gauge(
            _GAUGE_NAME,
            description="Health check status (1=healthy, 0=unhealthy)",
            labelnames=["name"],
        )
        self._latency_gauge = (
            metrics.gauge(
                _LATENCY_GAUGE_NAME,
                description="Health check latency in milliseconds",
                labelnames=["name"],
            )
            if export_latency
            else None
        )

    async def collect(self) -> None:
        """Run all health checks once and update metric gauges."""
        report = await self._registry.run_all()
        for name, status in report.results.items():
            self._gauge.set(1.0 if status.healthy else 0.0, labels={"name": name})
            if self._latency_gauge is not None:
                self._latency_gauge.set(status.latency_ms, labels={"name": name})

    async def collect_loop(self, interval: float = 30.0) -> None:
        """Continuously run health checks every *interval* seconds.

        This coroutine runs until cancelled.  Intended to be used as a
        background task::

            task = asyncio.create_task(exporter.collect_loop(interval=15.0))
            # later:
            task.cancel()

        Parameters
        ----------
        interval:
            Seconds between successive collection rounds.
        """
        while True:
            try:
                await self.collect()
            except Exception:
                logger.exception("PrometheusHealthExporter.collect() raised an exception")
            await asyncio.sleep(interval)


__all__ = ["PrometheusHealthExporter"]
