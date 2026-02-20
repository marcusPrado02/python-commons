"""Observability – Counter, Histogram, Gauge, Metrics ports."""
from __future__ import annotations

import abc
import dataclasses


@dataclasses.dataclass(frozen=True)
class MetricLabels:
    labels: dict[str, str] = dataclasses.field(default_factory=dict)


class Counter(abc.ABC):
    """Monotonically increasing counter."""

    @abc.abstractmethod
    def add(self, value: float = 1.0, labels: dict[str, str] | None = None) -> None: ...


class Histogram(abc.ABC):
    """Distribution / latency histogram."""

    @abc.abstractmethod
    def record(self, value: float, labels: dict[str, str] | None = None) -> None: ...


class Gauge(abc.ABC):
    """Up/down gauge."""

    @abc.abstractmethod
    def set(self, value: float, labels: dict[str, str] | None = None) -> None: ...

    @abc.abstractmethod
    def inc(self, labels: dict[str, str] | None = None) -> None: ...

    @abc.abstractmethod
    def dec(self, labels: dict[str, str] | None = None) -> None: ...


class Metrics(abc.ABC):
    """Port: factory for metric instruments."""

    @abc.abstractmethod
    def counter(self, name: str, description: str = "", unit: str = "") -> Counter: ...

    @abc.abstractmethod
    def histogram(self, name: str, description: str = "", unit: str = "ms", boundaries: list[float] | None = None) -> Histogram: ...

    @abc.abstractmethod
    def gauge(self, name: str, description: str = "", unit: str = "") -> Gauge: ...


__all__ = ["Counter", "Gauge", "Histogram", "MetricLabels", "Metrics"]
