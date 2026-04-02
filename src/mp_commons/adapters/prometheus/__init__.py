"""Prometheus adapter — metrics registry and health exporter.

Requires ``prometheus-client>=0.20``.  Install via::

    pip install 'mp-commons[prometheus]'
"""

from __future__ import annotations

from mp_commons.adapters.prometheus.health_exporter import PrometheusHealthExporter
from mp_commons.adapters.prometheus.metrics import PrometheusMetrics

__all__ = [
    "PrometheusHealthExporter",
    "PrometheusMetrics",
]
