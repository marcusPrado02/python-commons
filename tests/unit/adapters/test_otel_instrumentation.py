"""Unit tests for SQLAlchemy OTel instrumentation and Kafka trace propagation (O-01, O-02)."""
from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock, patch, call

import pytest

# ---------------------------------------------------------------------------
# Stub opentelemetry so tests run without the real library
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

    class _SpanKind:
        CLIENT = "CLIENT"
        SERVER = "SERVER"
        INTERNAL = "INTERNAL"
        PRODUCER = "PRODUCER"
        CONSUMER = "CONSUMER"

    class _StatusCode:
        OK = "OK"
        ERROR = "ERROR"

    _fake_tracer = MagicMock()
    otel_trace.get_tracer = MagicMock(return_value=_fake_tracer)
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

    sys.modules.setdefault("opentelemetry", otel)
    sys.modules.setdefault("opentelemetry.trace", otel_trace)
    sys.modules.setdefault("opentelemetry.context", otel_context)
    sys.modules.setdefault("opentelemetry.propagate", otel_propagate)
    sys.modules.setdefault("opentelemetry.propagators", otel_propagators)
    sys.modules.setdefault("opentelemetry.propagators.textmap", otel_propagators_textmap)


_build_otel_stub()

from mp_commons.adapters.opentelemetry.kafka_propagation import (  # noqa: E402
    inject_trace_headers,
    extract_trace_context,
)
from mp_commons.adapters.opentelemetry.sqlalchemy_instrumentation import (  # noqa: E402
    instrument_engine,
    uninstrument_engine,
    _before_cursor_execute,
    _after_cursor_execute,
    _sanitize_sql,
)


# ---------------------------------------------------------------------------
# SQLAlchemy instrumentation
# ---------------------------------------------------------------------------


class TestSQLAlchemyInstrumentation:
    def _make_engine(self) -> MagicMock:
        engine = MagicMock()
        engine.dialect.name = "postgresql"
        return engine

    def test_instrument_attaches_listeners(self):
        sqlalchemy_event = MagicMock()
        sqlalchemy_event.contains.return_value = False

        import mp_commons.adapters.opentelemetry.sqlalchemy_instrumentation as _mod

        with patch.object(_mod, "_get_tracer", return_value=MagicMock()):
            with patch.dict(sys.modules, {"sqlalchemy": MagicMock(), "sqlalchemy.event": sqlalchemy_event}):
                import importlib
                from unittest.mock import patch as _patch

                sa_mod = types.ModuleType("sqlalchemy")
                sa_mod.event = MagicMock()  # type: ignore[attr-defined]
                sa_mod.event.contains.return_value = False  # type: ignore[attr-defined]

                with _patch.dict(sys.modules, {"sqlalchemy": sa_mod}):
                    engine = self._make_engine()
                    engine.sync_engine = engine  # simulate sync engine attr
                    instrument_engine(engine)
                    sa_mod.event.listen.assert_called()

    def test_sanitize_sql_removes_named_params(self):
        sql = "SELECT * FROM users WHERE id = :user_id AND status = :status"
        result = _sanitize_sql(sql)
        assert ":user_id" not in result
        assert ":status" not in result
        assert "?" in result

    def test_sanitize_sql_removes_positional_params(self):
        result = _sanitize_sql("SELECT * FROM t WHERE id = $1 AND x = $2")
        assert "$1" not in result
        assert "$2" not in result

    def test_sanitize_sql_truncates_long_statements(self):
        long_sql = "SELECT " + "a, " * 1000 + "b FROM t"
        result = _sanitize_sql(long_sql)
        assert len(result) <= 2000

    def test_before_cursor_execute_starts_span(self):
        tracer = MagicMock()
        span_ctx = MagicMock()
        span_ctx.__enter__ = MagicMock(return_value=span_ctx)
        tracer.start_span.return_value = span_ctx

        conn = MagicMock()
        conn.engine.dialect.name = "postgresql"
        conn._otel_spans = []

        import mp_commons.adapters.opentelemetry.sqlalchemy_instrumentation as _mod

        with patch.object(_mod, "_get_tracer", return_value=tracer):
            _mod._before_cursor_execute(conn, None, "SELECT 1", None, None, False)

        tracer.start_span.assert_called_once()
        call_kwargs = tracer.start_span.call_args
        assert "db.SELECT" in call_kwargs[0][0]

    def test_after_cursor_execute_ends_span(self):
        span_ctx = MagicMock()
        span_ctx.__exit__ = MagicMock(return_value=False)

        conn = MagicMock()
        conn._otel_spans = [span_ctx]

        _after_cursor_execute(conn, None, "SELECT 1", None, None, False)
        span_ctx.__exit__.assert_called_once_with(None, None, None)
        assert len(conn._otel_spans) == 0


# ---------------------------------------------------------------------------
# Kafka trace propagation
# ---------------------------------------------------------------------------


class TestKafkaTracePropagation:
    def test_inject_adds_traceparent_header(self):
        headers: list = []
        inject_trace_headers(headers)
        keys = [k if isinstance(k, str) else k.decode() for k, _ in headers]
        assert "traceparent" in keys

    def test_inject_is_noop_when_no_propagator(self):
        import mp_commons.adapters.opentelemetry.kafka_propagation as _mod

        with patch.object(_mod, "_get_propagator", return_value=None):
            headers: list = []
            _mod.inject_trace_headers(headers)
            assert headers == []

    def test_extract_attaches_context(self):
        headers = [("traceparent", b"00-traceid-spanid-01")]
        token = extract_trace_context(headers)
        assert token == "token-123"

    def test_extract_returns_none_on_empty_headers(self):
        token = extract_trace_context([])
        assert token is None

    def test_extract_returns_none_when_no_propagator(self):
        import mp_commons.adapters.opentelemetry.kafka_propagation as _mod

        with patch.object(_mod, "_get_propagator", return_value=None):
            token = _mod.extract_trace_context([("traceparent", b"00-x-y-01")])
            assert token is None

    def test_inject_does_not_raise_on_propagator_error(self):
        import mp_commons.adapters.opentelemetry.kafka_propagation as _mod

        bad_propagator = MagicMock()
        bad_propagator.inject.side_effect = RuntimeError("otel broken")
        with patch.object(_mod, "_get_propagator", return_value=bad_propagator):
            headers: list = []
            _mod.inject_trace_headers(headers)  # must not raise
