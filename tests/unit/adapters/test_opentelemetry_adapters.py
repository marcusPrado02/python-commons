"""Unit tests for OpenTelemetry adapters (§35.1–35.5) — no otel install."""
from __future__ import annotations

import asyncio
import sys
from contextlib import contextmanager
from typing import Any, Iterator
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Mock OpenTelemetry modules — installed into sys.modules so adapters can
# import them without the real opentelemetry package.
# ---------------------------------------------------------------------------


def _build_otel_mocks() -> dict[str, Any]:
    """Return fake opentelemetry sub-modules dict + named refs under '_' keys."""

    class _StatusCode:
        OK = "OK"
        ERROR = "ERROR"

    class _SpanKind:
        INTERNAL = "INTERNAL"
        SERVER = "SERVER"
        CLIENT = "CLIENT"
        PRODUCER = "PRODUCER"
        CONSUMER = "CONSUMER"

    mock_span_ctx = MagicMock()
    mock_span_ctx.is_valid = True
    mock_span_ctx.trace_id = 0xABCD1234ABCD1234ABCD1234ABCD1234
    mock_span_ctx.span_id = 0x1234ABCD1234ABCD

    mock_span = MagicMock()
    mock_span.get_span_context = MagicMock(return_value=mock_span_ctx)

    mock_trace = MagicMock()
    mock_trace.StatusCode = _StatusCode
    mock_trace.SpanKind = _SpanKind
    mock_trace.get_current_span = MagicMock(return_value=mock_span)

    mock_tracer = MagicMock()

    @contextmanager
    def _start_span(name: str, kind: Any = None, attributes: Any = None) -> Iterator[MagicMock]:
        inner = MagicMock()
        inner.set_attribute = MagicMock()
        inner.set_status = MagicMock()
        inner.record_exception = MagicMock()
        inner.end = MagicMock()
        yield inner

    mock_tracer.start_as_current_span = _start_span
    mock_trace.get_tracer = MagicMock(return_value=mock_tracer)

    mock_meter = MagicMock()
    mock_meter.create_counter = MagicMock(return_value=MagicMock())
    mock_meter.create_histogram = MagicMock(return_value=MagicMock())
    mock_metrics = MagicMock()
    mock_metrics.get_meter = MagicMock(return_value=mock_meter)

    mock_propagate = MagicMock()
    mock_propagate.inject = MagicMock()
    mock_propagate.extract = MagicMock(return_value=MagicMock())

    mock_otel = MagicMock()
    mock_otel.trace = mock_trace
    mock_otel.metrics = mock_metrics

    return {
        "opentelemetry": mock_otel,
        "opentelemetry.trace": mock_trace,
        "opentelemetry.metrics": mock_metrics,
        "opentelemetry.propagate": mock_propagate,
        "opentelemetry.propagators": MagicMock(),
        "opentelemetry.propagators.b3": MagicMock(),
        "opentelemetry.propagators.tracecontext": MagicMock(),
        "_mock_trace": mock_trace,
        "_mock_tracer": mock_tracer,
        "_mock_metrics": mock_metrics,
        "_mock_meter": mock_meter,
        "_mock_propagate": mock_propagate,
        "_mock_span": mock_span,
        "_mock_span_ctx": mock_span_ctx,
    }


def _install_otel_mocks() -> tuple[dict[str, Any], dict[str, Any]]:
    """Patch sys.modules, flush adapter module cache.  Returns (mocks, originals)."""
    mocks = _build_otel_mocks()
    modules_to_inject = {k: v for k, v in mocks.items() if not k.startswith("_")}

    originals: dict[str, Any] = {}
    for name in modules_to_inject:
        originals[name] = sys.modules.pop(name, None)

    adapter_cache: dict[str, Any] = {}
    for key in list(sys.modules.keys()):
        if key.startswith("mp_commons.adapters.opentelemetry"):
            adapter_cache[key] = sys.modules.pop(key)
    originals["__adapter_cache__"] = adapter_cache  # type: ignore[assignment]

    sys.modules.update(modules_to_inject)
    return mocks, originals


def _restore_otel_mocks(originals: dict[str, Any]) -> None:
    adapter_cache: dict[str, Any] = originals.pop("__adapter_cache__", {})
    for name, mod in originals.items():
        sys.modules.pop(name, None)
        if mod is not None:
            sys.modules[name] = mod
    for key, mod in adapter_cache.items():
        sys.modules[key] = mod


# ---------------------------------------------------------------------------
# §35.1 OtelTracer
# ---------------------------------------------------------------------------


class TestOtelTracer:
    def test_init_calls_get_tracer(self) -> None:
        mocks, originals = _install_otel_mocks()
        try:
            from mp_commons.adapters.opentelemetry.tracer import OtelTracer
            OtelTracer(service_name="my-svc")
            mocks["_mock_trace"].get_tracer.assert_called_once_with("my-svc")
        finally:
            _restore_otel_mocks(originals)

    def test_start_span_yields_span(self) -> None:
        mocks, originals = _install_otel_mocks()
        try:
            from mp_commons.adapters.opentelemetry.tracer import OtelTracer
            from mp_commons.observability.tracing import Span
            tracer = OtelTracer(service_name="svc")
            with tracer.start_span("op") as span:
                assert isinstance(span, Span)
        finally:
            _restore_otel_mocks(originals)

    def test_span_set_attribute(self) -> None:
        mocks, originals = _install_otel_mocks()
        try:
            from mp_commons.adapters.opentelemetry.tracer import OtelTracer
            tracer = OtelTracer(service_name="svc")
            with tracer.start_span("op") as span:
                span.set_attribute("key", "value")
                span._span.set_attribute.assert_called_once_with("key", "value")  # noqa: SLF001
        finally:
            _restore_otel_mocks(originals)

    def test_span_set_status_ok(self) -> None:
        mocks, originals = _install_otel_mocks()
        try:
            from mp_commons.adapters.opentelemetry.tracer import OtelTracer
            tracer = OtelTracer(service_name="svc")
            with tracer.start_span("op") as span:
                span.set_status_ok()
                span._span.set_status.assert_called()  # noqa: SLF001
        finally:
            _restore_otel_mocks(originals)

    def test_span_record_exception(self) -> None:
        mocks, originals = _install_otel_mocks()
        try:
            from mp_commons.adapters.opentelemetry.tracer import OtelTracer
            tracer = OtelTracer(service_name="svc")
            exc = ValueError("boom")
            with tracer.start_span("op") as span:
                span.record_exception(exc)
                span._span.record_exception.assert_called_once_with(exc)  # noqa: SLF001
        finally:
            _restore_otel_mocks(originals)

    def test_start_async_span_yields_span(self) -> None:
        mocks, originals = _install_otel_mocks()
        try:
            from mp_commons.adapters.opentelemetry.tracer import OtelTracer
            from mp_commons.observability.tracing import Span
            tracer = OtelTracer(service_name="svc")

            async def run() -> None:
                async with tracer.start_async_span("async-op") as span:
                    assert isinstance(span, Span)
            asyncio.run(run())
        finally:
            _restore_otel_mocks(originals)

    def test_require_otel_raises_when_missing(self) -> None:
        # Remove otel from sys.modules temporarily
        removed: dict[str, Any] = {}
        for key in list(sys.modules.keys()):
            if "opentelemetry" in key:
                removed[key] = sys.modules.pop(key)
        # also flush adapter
        for key in list(sys.modules.keys()):
            if key.startswith("mp_commons.adapters.opentelemetry"):
                removed[key] = sys.modules.pop(key)

        import builtins
        real_import = builtins.__import__

        def block(name: str, *args: Any, **kw: Any) -> Any:
            if name.startswith("opentelemetry"):
                raise ImportError("blocked")
            return real_import(name, *args, **kw)

        try:
            with patch("builtins.__import__", side_effect=block):
                import importlib
                import mp_commons.adapters.opentelemetry.tracer as tracer_mod  # noqa: PLC0415
                importlib.reload(tracer_mod)
                with pytest.raises(ImportError, match="mp-commons\\[otel\\]"):
                    tracer_mod._require_otel()
        finally:
            sys.modules.update(removed)


# ---------------------------------------------------------------------------
# §35.2 OtelMetrics
# ---------------------------------------------------------------------------


class TestOtelMetrics:
    def test_init_calls_get_meter(self) -> None:
        mocks, originals = _install_otel_mocks()
        try:
            from mp_commons.adapters.opentelemetry.metrics import OtelMetrics
            OtelMetrics(meter_name="test-meter")
            mocks["_mock_metrics"].get_meter.assert_called_once_with("test-meter")
        finally:
            _restore_otel_mocks(originals)

    def test_counter_creates_and_delegates_add(self) -> None:
        mocks, originals = _install_otel_mocks()
        try:
            from mp_commons.adapters.opentelemetry.metrics import OtelMetrics
            m = OtelMetrics()
            c = m.counter("requests", description="Total requests")
            mocks["_mock_meter"].create_counter.assert_called_once()
            c.add(5.0, labels={"route": "/api"})
            mocks["_mock_meter"].create_counter.return_value.add.assert_called_once_with(
                5.0, attributes={"route": "/api"}
            )
        finally:
            _restore_otel_mocks(originals)

    def test_counter_add_default_value(self) -> None:
        mocks, originals = _install_otel_mocks()
        try:
            from mp_commons.adapters.opentelemetry.metrics import OtelMetrics
            m = OtelMetrics()
            c = m.counter("hits")
            c.add()
            mocks["_mock_meter"].create_counter.return_value.add.assert_called_once_with(
                1.0, attributes=None
            )
        finally:
            _restore_otel_mocks(originals)

    def test_histogram_creates_and_delegates_record(self) -> None:
        mocks, originals = _install_otel_mocks()
        try:
            from mp_commons.adapters.opentelemetry.metrics import OtelMetrics
            m = OtelMetrics()
            h = m.histogram("latency", unit="ms")
            mocks["_mock_meter"].create_histogram.assert_called_once()
            h.record(42.0)
            mocks["_mock_meter"].create_histogram.return_value.record.assert_called_once_with(
                42.0, attributes=None
            )
        finally:
            _restore_otel_mocks(originals)

    def test_gauge_set_inc_dec(self) -> None:
        mocks, originals = _install_otel_mocks()
        try:
            from mp_commons.adapters.opentelemetry.metrics import OtelMetrics
            m = OtelMetrics()
            g = m.gauge("connections")
            g.set(10.0)
            assert g._value == 10.0  # noqa: SLF001
            g.inc()
            assert g._value == 11.0  # noqa: SLF001
            g.dec()
            assert g._value == 10.0  # noqa: SLF001
        finally:
            _restore_otel_mocks(originals)


# ---------------------------------------------------------------------------
# §35.3 OtelPropagator
# ---------------------------------------------------------------------------


class TestOtelPropagator:
    def test_inject_calls_otel_inject(self) -> None:
        mocks, originals = _install_otel_mocks()
        try:
            from mp_commons.adapters.opentelemetry.propagator import OtelPropagator
            p = OtelPropagator()
            headers: dict[str, str] = {}
            result = p.inject(headers)
            mocks["_mock_propagate"].inject.assert_called_once_with(headers)
            assert result is headers
        finally:
            _restore_otel_mocks(originals)

    def test_extract_calls_otel_extract(self) -> None:
        mocks, originals = _install_otel_mocks()
        try:
            from mp_commons.adapters.opentelemetry.propagator import OtelPropagator
            p = OtelPropagator()
            headers = {"traceparent": "00-abc-def-01"}
            result = p.extract(headers)
            mocks["_mock_propagate"].extract.assert_called_once_with(headers)
            assert "context" in result
        finally:
            _restore_otel_mocks(originals)

    def test_inject_propagates_header_mutation(self) -> None:
        mocks, originals = _install_otel_mocks()
        try:
            def _side(d: dict, **_: Any) -> None:
                d["traceparent"] = "00-trace-span-01"
            mocks["_mock_propagate"].inject.side_effect = _side

            from mp_commons.adapters.opentelemetry.propagator import OtelPropagator
            p = OtelPropagator()
            headers: dict[str, str] = {}
            result = p.inject(headers)
            assert result["traceparent"] == "00-trace-span-01"
        finally:
            _restore_otel_mocks(originals)


# ---------------------------------------------------------------------------
# §35.4 OtelLoggingEnricher
# ---------------------------------------------------------------------------


class TestOtelLoggingEnricher:
    def test_enricher_injects_valid_ids(self) -> None:
        mocks, originals = _install_otel_mocks()
        try:
            from mp_commons.adapters.opentelemetry.enricher import OtelLoggingEnricher
            enricher = OtelLoggingEnricher()
            result = enricher(None, None, {"event": "user.login"})
            assert "trace_id" in result
            assert "span_id" in result
            assert len(result["trace_id"]) == 32
            assert len(result["span_id"]) == 16
        finally:
            _restore_otel_mocks(originals)

    def test_enricher_noop_when_span_invalid(self) -> None:
        mocks, originals = _install_otel_mocks()
        try:
            # Make span context invalid
            mocks["_mock_span_ctx"].is_valid = False
            import importlib
            import mp_commons.adapters.opentelemetry.enricher as enricher_mod
            importlib.reload(enricher_mod)
            enricher = enricher_mod.OtelLoggingEnricher()
            result = enricher(None, None, {"event": "x"})
            assert "trace_id" not in result
            assert "span_id" not in result
        finally:
            _restore_otel_mocks(originals)

    def test_enricher_noop_when_otel_unavailable(self) -> None:
        """OtelLoggingEnricher must silently swallow ImportError."""
        # Remove otel from sys.modules temporarily and flush adapter
        removed: dict[str, Any] = {}
        for key in list(sys.modules.keys()):
            if "opentelemetry" in key:
                removed[key] = sys.modules.pop(key)
        for key in list(sys.modules.keys()):
            if key.startswith("mp_commons.adapters.opentelemetry"):
                removed[key] = sys.modules.pop(key)

        import builtins
        real_import = builtins.__import__

        def block(name: str, *args: Any, **kw: Any) -> Any:
            if name.startswith("opentelemetry"):
                raise ImportError("no otel")
            return real_import(name, *args, **kw)

        import importlib
        import mp_commons.adapters.opentelemetry.enricher as enricher_mod

        try:
            with patch("builtins.__import__", side_effect=block):
                importlib.reload(enricher_mod)
                enricher = enricher_mod.OtelLoggingEnricher()
                result = enricher(None, None, {"event": "ping"})
                assert result == {"event": "ping"}
        finally:
            sys.modules.update(removed)

    def test_enricher_returns_event_dict_unmodified_type(self) -> None:
        mocks, originals = _install_otel_mocks()
        try:
            from mp_commons.adapters.opentelemetry.enricher import OtelLoggingEnricher
            enricher = OtelLoggingEnricher()
            event_dict: dict[str, Any] = {"event": "test", "level": "info"}
            result = enricher(None, None, event_dict)
            assert isinstance(result, dict)
            assert result["event"] == "test"
        finally:
            _restore_otel_mocks(originals)
