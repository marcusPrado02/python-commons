"""Observability – Tracer, Span, SpanKind, TracePropagator ports."""
from __future__ import annotations

import abc
import contextlib
from enum import Enum
from typing import Any, AsyncIterator, Iterator, Protocol


class SpanKind(str, Enum):
    INTERNAL = "INTERNAL"
    SERVER = "SERVER"
    CLIENT = "CLIENT"
    PRODUCER = "PRODUCER"
    CONSUMER = "CONSUMER"


class Span(abc.ABC):
    """Represents an active trace span."""

    @abc.abstractmethod
    def set_attribute(self, key: str, value: Any) -> None: ...

    @abc.abstractmethod
    def set_status_ok(self) -> None: ...

    @abc.abstractmethod
    def record_exception(self, exc: Exception) -> None: ...

    @abc.abstractmethod
    def end(self) -> None: ...

    def __enter__(self) -> "Span":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if exc_val is not None:
            self.record_exception(exc_val)
        else:
            self.set_status_ok()
        self.end()


class Tracer(abc.ABC):
    """Port: create and manage spans."""

    @abc.abstractmethod
    @contextlib.contextmanager
    def start_span(self, name: str, kind: SpanKind = SpanKind.INTERNAL, attributes: dict[str, Any] | None = None) -> Iterator[Span]: ...

    @abc.abstractmethod
    @contextlib.asynccontextmanager
    async def start_async_span(self, name: str, kind: SpanKind = SpanKind.INTERNAL, attributes: dict[str, Any] | None = None) -> AsyncIterator[Span]: ...


class TracePropagator(Protocol):
    """Port: inject/extract trace context from transport headers."""

    def inject(self, headers: dict[str, str]) -> dict[str, str]: ...

    def extract(self, headers: dict[str, str]) -> dict[str, Any]: ...


__all__ = ["Span", "SpanKind", "TracePropagator", "Tracer"]
