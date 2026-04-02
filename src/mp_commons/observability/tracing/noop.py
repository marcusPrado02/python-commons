"""Observability – NoopTracer."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
import contextlib
from typing import Any

from mp_commons.observability.tracing.ports import Span, SpanKind, Tracer


class _NoopSpan(Span):
    def set_attribute(self, key: str, value: Any) -> None:
        pass

    def set_status_ok(self) -> None:
        pass

    def record_exception(self, exc: Exception) -> None:
        pass

    def end(self) -> None:
        pass


class NoopTracer(Tracer):
    """Silent no-op tracer."""

    @contextlib.contextmanager
    def start_span(
        self,
        name: str,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: dict[str, Any] | None = None,
    ) -> Iterator[Span]:
        yield _NoopSpan()

    @contextlib.asynccontextmanager
    async def start_async_span(
        self,
        name: str,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: dict[str, Any] | None = None,
    ) -> AsyncIterator[Span]:
        yield _NoopSpan()


__all__ = ["NoopTracer"]
