"""Unit tests for observability tracing (§22)."""

from __future__ import annotations

from typing import Any, Iterator

import pytest

from mp_commons.observability.tracing import (
    NoopTracer,
    Span,
    SpanKind,
    TracePropagator,
    Tracer,
)


# ---------------------------------------------------------------------------
# Minimal Span stub implementing the ABC
# ---------------------------------------------------------------------------


class _StubSpan(Span):
    def __init__(self) -> None:
        self.attributes: dict[str, Any] = {}
        self.exceptions: list[Exception] = []
        self.status_ok_set = False
        self.ended = False

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def set_status_ok(self) -> None:
        self.status_ok_set = True

    def record_exception(self, exc: Exception) -> None:
        self.exceptions.append(exc)

    def end(self) -> None:
        self.ended = True


# ---------------------------------------------------------------------------
# §22.1  Span ABC
# ---------------------------------------------------------------------------


class TestSpanProtocol:
    def test_set_attribute(self) -> None:
        span = _StubSpan()
        span.set_attribute("http.method", "GET")
        assert span.attributes["http.method"] == "GET"

    def test_record_exception(self) -> None:
        span = _StubSpan()
        exc = ValueError("oops")
        span.record_exception(exc)
        assert exc in span.exceptions

    def test_set_status_ok(self) -> None:
        span = _StubSpan()
        span.set_status_ok()
        assert span.status_ok_set is True

    def test_end_marks_ended(self) -> None:
        span = _StubSpan()
        span.end()
        assert span.ended is True

    def test_context_manager_calls_end_on_success(self) -> None:
        span = _StubSpan()
        with span:
            pass
        assert span.ended is True
        assert span.status_ok_set is True

    def test_context_manager_records_exception(self) -> None:
        span = _StubSpan()
        exc = RuntimeError("boom")
        with pytest.raises(RuntimeError):
            with span:
                raise exc
        assert exc in span.exceptions
        assert span.ended is True

    def test_context_manager_returns_span(self) -> None:
        span = _StubSpan()
        with span as s:
            assert s is span


# ---------------------------------------------------------------------------
# §22.2  Tracer ABC – minimal stub
# ---------------------------------------------------------------------------


import contextlib


class _StubTracer(Tracer):
    def __init__(self) -> None:
        self.started_spans: list[tuple[str, SpanKind]] = []

    @contextlib.contextmanager
    def start_span(
        self,
        name: str,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: dict[str, Any] | None = None,
    ) -> Iterator[Span]:
        self.started_spans.append((name, kind))
        yield _StubSpan()

    @contextlib.asynccontextmanager
    async def start_async_span(
        self,
        name: str,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: dict[str, Any] | None = None,
    ):
        self.started_spans.append((name, kind))
        yield _StubSpan()


class TestTracerProtocol:
    def test_start_span_yields_span(self) -> None:
        tracer = _StubTracer()
        with tracer.start_span("test-op") as span:
            assert isinstance(span, Span)

    def test_start_span_records_name(self) -> None:
        tracer = _StubTracer()
        with tracer.start_span("my-operation"):
            pass
        assert tracer.started_spans[0][0] == "my-operation"

    def test_start_span_default_kind(self) -> None:
        tracer = _StubTracer()
        with tracer.start_span("x"):
            pass
        assert tracer.started_spans[0][1] == SpanKind.INTERNAL

    def test_start_span_custom_kind(self) -> None:
        tracer = _StubTracer()
        with tracer.start_span("rpc", kind=SpanKind.CLIENT):
            pass
        assert tracer.started_spans[0][1] == SpanKind.CLIENT

    def test_start_async_span(self) -> None:
        import asyncio

        tracer = _StubTracer()

        async def go() -> Span:
            async with tracer.start_async_span("async-op") as span:
                return span

        span = asyncio.run(go())
        assert isinstance(span, Span)
        assert tracer.started_spans[0][0] == "async-op"


# ---------------------------------------------------------------------------
# §22.3  NoopTracer / NoopSpan – no-ops
# ---------------------------------------------------------------------------


class TestNoopTracer:
    def test_start_span_does_not_raise(self) -> None:
        tracer = NoopTracer()
        with tracer.start_span("op") as span:
            span.set_attribute("k", "v")
            span.set_status_ok()

    def test_start_span_span_end_does_not_raise(self) -> None:
        tracer = NoopTracer()
        with tracer.start_span("op") as span:
            span.end()

    def test_start_async_span_does_not_raise(self) -> None:
        import asyncio

        async def go() -> None:
            async with NoopTracer().start_async_span("op") as span:
                span.set_attribute("x", 1)
                span.record_exception(ValueError("noop"))

        asyncio.run(go())

    def test_record_exception_no_raise(self) -> None:
        tracer = NoopTracer()
        with tracer.start_span("op") as span:
            span.record_exception(Exception("silent"))

    def test_span_is_span_instance(self) -> None:
        tracer = NoopTracer()
        with tracer.start_span("x") as span:
            assert isinstance(span, Span)

    def test_noop_tracer_is_tracer(self) -> None:
        assert isinstance(NoopTracer(), Tracer)

    def test_context_manager_calls_end_implicitly(self) -> None:
        # Context manager must exit cleanly (end is called via __exit__)
        tracer = NoopTracer()
        with tracer.start_span("op"):
            pass  # No assertion — just must not raise


# ---------------------------------------------------------------------------
# §22  SpanKind values
# ---------------------------------------------------------------------------


class TestSpanKind:
    def test_all_kinds_defined(self) -> None:
        expected = {"INTERNAL", "SERVER", "CLIENT", "PRODUCER", "CONSUMER"}
        assert {k.value for k in SpanKind} == expected

    def test_kind_is_string(self) -> None:
        assert SpanKind.SERVER == "SERVER"
