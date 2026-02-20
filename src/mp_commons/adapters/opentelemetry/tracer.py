"""OpenTelemetry adapter – OtelTracer."""
from __future__ import annotations

import contextlib
from typing import Any, AsyncIterator, Iterator

from mp_commons.observability.tracing import Span, SpanKind, Tracer


def _require_otel() -> None:
    try:
        import opentelemetry  # noqa: F401
    except ImportError as exc:
        raise ImportError("Install 'mp-commons[otel]' to use the OpenTelemetry adapter") from exc


class _OtelSpan(Span):
    def __init__(self, span: Any) -> None:
        self._span = span

    def set_attribute(self, key: str, value: Any) -> None:
        self._span.set_attribute(key, value)

    def set_status_ok(self) -> None:
        from opentelemetry.trace import StatusCode  # type: ignore[import-untyped]
        self._span.set_status(StatusCode.OK)

    def record_exception(self, exc: Exception) -> None:
        self._span.record_exception(exc)
        from opentelemetry.trace import StatusCode  # type: ignore[import-untyped]
        self._span.set_status(StatusCode.ERROR, str(exc))

    def end(self) -> None:
        self._span.end()


class OtelTracer(Tracer):
    """OpenTelemetry tracer adapter."""

    def __init__(self, service_name: str = "service") -> None:
        _require_otel()
        from opentelemetry import trace  # type: ignore[import-untyped]
        self._tracer = trace.get_tracer(service_name)

    @contextlib.contextmanager
    def start_span(self, name: str, kind: SpanKind = SpanKind.INTERNAL, attributes: dict[str, Any] | None = None) -> Iterator[Span]:
        from opentelemetry.trace import SpanKind as OtelKind  # type: ignore[import-untyped]
        _KIND_MAP = {
            SpanKind.INTERNAL: OtelKind.INTERNAL, SpanKind.SERVER: OtelKind.SERVER,
            SpanKind.CLIENT: OtelKind.CLIENT, SpanKind.PRODUCER: OtelKind.PRODUCER,
            SpanKind.CONSUMER: OtelKind.CONSUMER,
        }
        with self._tracer.start_as_current_span(name, kind=_KIND_MAP.get(kind, OtelKind.INTERNAL), attributes=attributes) as span:
            yield _OtelSpan(span)

    @contextlib.asynccontextmanager
    async def start_async_span(self, name: str, kind: SpanKind = SpanKind.INTERNAL, attributes: dict[str, Any] | None = None) -> AsyncIterator[Span]:
        with self.start_span(name, kind, attributes) as span:
            yield span


__all__ = ["OtelTracer"]
