"""Unit tests for NATS traceparent propagation (O-03)."""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Build minimal OpenTelemetry stubs (same pattern as kafka propagation tests)
# ---------------------------------------------------------------------------


def _build_otel_stub() -> None:
    if "opentelemetry" in sys.modules:
        return

    otel = types.ModuleType("opentelemetry")
    otel_trace = types.ModuleType("opentelemetry.trace")
    otel_context = types.ModuleType("opentelemetry.context")
    otel_propagate = types.ModuleType("opentelemetry.propagate")
    otel_propagators = types.ModuleType("opentelemetry.propagators")
    otel_propagators_textmap = types.ModuleType("opentelemetry.propagators.textmap")

    # SpanKind / StatusCode required by sqlalchemy_instrumentation
    class _SpanKind:
        CLIENT = "CLIENT"
        SERVER = "SERVER"
        INTERNAL = "INTERNAL"
        PRODUCER = "PRODUCER"
        CONSUMER = "CONSUMER"

    class _StatusCode:
        OK = "OK"
        ERROR = "ERROR"

    otel_trace.get_tracer = MagicMock(return_value=MagicMock())
    otel_trace.SpanKind = _SpanKind
    otel_trace.StatusCode = _StatusCode

    class _FakePropagator:
        def inject(self, carrier: object) -> None:
            carrier.set("traceparent", "00-traceid-spanid-01")  # type: ignore[attr-defined]

        def extract(self, carrier: object) -> dict:
            return {"traceparent": carrier.get("traceparent")}  # type: ignore[attr-defined]

    otel_propagate.get_global_textmap = MagicMock(return_value=_FakePropagator())
    otel_context.attach = MagicMock(return_value="token-123")
    otel_propagators_textmap.DefaultTextMapPropagator = MagicMock

    for name, mod in [
        ("opentelemetry", otel),
        ("opentelemetry.trace", otel_trace),
        ("opentelemetry.context", otel_context),
        ("opentelemetry.propagate", otel_propagate),
        ("opentelemetry.propagators", otel_propagators),
        ("opentelemetry.propagators.textmap", otel_propagators_textmap),
    ]:
        sys.modules.setdefault(name, mod)


_build_otel_stub()

import mp_commons.adapters.opentelemetry.nats_propagation as _mod

# ---------------------------------------------------------------------------
# inject_trace_headers
# ---------------------------------------------------------------------------


class TestInjectTraceHeaders:
    def test_inject_adds_traceparent(self):
        headers: dict[str, str] = {}
        _mod.inject_trace_headers(headers)
        assert "traceparent" in headers

    def test_inject_is_noop_when_no_propagator(self):
        with patch.object(_mod, "_get_propagator", return_value=None):
            headers: dict[str, str] = {}
            _mod.inject_trace_headers(headers)
            assert headers == {}

    def test_inject_does_not_raise_on_propagator_error(self):
        bad = MagicMock()
        bad.inject.side_effect = RuntimeError("oops")
        with patch.object(_mod, "_get_propagator", return_value=bad):
            headers: dict[str, str] = {}
            _mod.inject_trace_headers(headers)  # must not raise

    def test_inject_preserves_existing_headers(self):
        headers = {"content-type": "application/json"}
        _mod.inject_trace_headers(headers)
        assert headers["content-type"] == "application/json"
        assert "traceparent" in headers

    def test_inject_sets_string_value(self):
        headers: dict[str, str] = {}
        _mod.inject_trace_headers(headers)
        assert isinstance(headers.get("traceparent"), str)


# ---------------------------------------------------------------------------
# extract_trace_context
# ---------------------------------------------------------------------------


class TestExtractTraceContext:
    def test_extract_returns_token(self):
        headers = {"traceparent": "00-traceid-spanid-01"}
        token = _mod.extract_trace_context(headers)
        assert token == "token-123"

    def test_extract_returns_none_for_empty_headers(self):
        token = _mod.extract_trace_context({})
        assert token is None

    def test_extract_returns_none_for_none_headers(self):
        token = _mod.extract_trace_context(None)
        assert token is None

    def test_extract_is_noop_when_no_propagator(self):
        with patch.object(_mod, "_get_propagator", return_value=None):
            token = _mod.extract_trace_context({"traceparent": "00-x-y-01"})
            assert token is None

    def test_extract_is_noop_when_no_context_api(self):
        with patch.object(_mod, "_get_context_api", return_value=None):
            token = _mod.extract_trace_context({"traceparent": "00-x-y-01"})
            assert token is None

    def test_extract_does_not_raise_on_error(self):
        bad_ctx = MagicMock()
        bad_ctx.attach.side_effect = RuntimeError("ctx broken")
        with patch.object(_mod, "_get_context_api", return_value=bad_ctx):
            token = _mod.extract_trace_context({"traceparent": "00-x-y-01"})
            assert token is None


# ---------------------------------------------------------------------------
# _NatsHeaderCarrier
# ---------------------------------------------------------------------------


class TestNatsHeaderCarrier:
    def _make(self, data: dict) -> object:
        from mp_commons.adapters.opentelemetry.nats_propagation import _NatsHeaderCarrier

        return _NatsHeaderCarrier(data)

    def test_get_existing_key(self):
        carrier = self._make({"traceparent": "00-abc-def-01"})
        assert carrier.get("traceparent") == ["00-abc-def-01"]

    def test_get_missing_key_returns_empty_list(self):
        carrier = self._make({})
        assert carrier.get("traceparent") == []

    def test_set_adds_key(self):
        data: dict = {}
        carrier = self._make(data)
        carrier.set("traceparent", "00-aaa-bbb-01")
        assert data["traceparent"] == "00-aaa-bbb-01"

    def test_keys_returns_all_keys(self):
        data = {"a": "1", "b": "2"}
        carrier = self._make(data)
        assert set(carrier.keys()) == {"a", "b"}
