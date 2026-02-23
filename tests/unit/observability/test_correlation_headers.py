"""Tests for §19.3 – CorrelationContext.set_from_headers()."""
from __future__ import annotations

import re

import pytest

from mp_commons.observability.correlation.context import CorrelationContext


@pytest.fixture(autouse=True)
def _clear_ctx():
    CorrelationContext.clear()
    yield
    CorrelationContext.clear()


class TestSetFromHeaders:
    def test_picks_x_correlation_id(self) -> None:
        ctx = CorrelationContext.set_from_headers({"X-Correlation-ID": "abc-123"})
        assert ctx.correlation_id == "abc-123"

    def test_falls_back_to_x_request_id(self) -> None:
        ctx = CorrelationContext.set_from_headers({"X-Request-ID": "req-999"})
        assert ctx.correlation_id == "req-999"

    def test_generates_uuid_when_no_id_header(self) -> None:
        ctx = CorrelationContext.set_from_headers({})
        assert re.match(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            ctx.correlation_id,
        )

    def test_case_insensitive_correlation_id(self) -> None:
        ctx = CorrelationContext.set_from_headers({"x-correlation-id": "lower-case"})
        assert ctx.correlation_id == "lower-case"

    def test_case_insensitive_request_id(self) -> None:
        ctx = CorrelationContext.set_from_headers({"x-request-id": "lower-req"})
        assert ctx.correlation_id == "lower-req"

    def test_x_correlation_id_wins_over_x_request_id(self) -> None:
        ctx = CorrelationContext.set_from_headers(
            {"X-Correlation-ID": "corr", "X-Request-ID": "req"}
        )
        assert ctx.correlation_id == "corr"

    def test_parses_w3c_traceparent(self) -> None:
        trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"
        parent_id = "00f067aa0ba902b7"
        traceparent = f"00-{trace_id}-{parent_id}-01"
        ctx = CorrelationContext.set_from_headers({"traceparent": traceparent})
        assert ctx.trace_id == trace_id

    def test_case_insensitive_traceparent(self) -> None:
        trace_id = "aaaabbbbccccdddd1111222233334444"
        ctx = CorrelationContext.set_from_headers(
            {"TRACEPARENT": f"00-{trace_id}-0000000000000000-00"}
        )
        assert ctx.trace_id == trace_id

    def test_stores_context_in_correlation_context_get(self) -> None:
        ctx = CorrelationContext.set_from_headers({"X-Correlation-ID": "stored-id"})
        assert CorrelationContext.get() is ctx

    def test_empty_traceparent_does_not_raise(self) -> None:
        ctx = CorrelationContext.set_from_headers(
            {"traceparent": "invalid-garbage", "X-Correlation-ID": "safe"}
        )
        assert ctx.correlation_id == "safe"
        # trace_id may be None or some default – just must not raise
