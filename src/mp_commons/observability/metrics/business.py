"""Observability – BusinessMetric."""
from __future__ import annotations

import dataclasses

from mp_commons.observability.metrics.ports import Metrics


@dataclasses.dataclass(frozen=True)
class BusinessMetric:
    """Declare a domain-level metric that maps to a backend metric."""
    name: str
    description: str
    unit: str = ""
    labels: tuple[str, ...] = ()

    def record(self, metrics: Metrics, value: float, **label_values: str) -> None:
        """Record this metric using the provided ``Metrics`` facade."""
        hist = metrics.histogram(self.name, self.description, self.unit)
        hist.record(value, labels=dict(label_values) if label_values else None)


__all__ = ["BusinessMetric"]
