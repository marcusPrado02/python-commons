"""Unit tests – HTTP adapter (§32.1–32.4)."""
from __future__ import annotations

import asyncio
import dataclasses
from typing import Any

import httpx
import pytest
import respx

from mp_commons.adapters.http.client import HttpxHttpClient
from mp_commons.adapters.http.retry_client import RetryingHttpClient
from mp_commons.adapters.http.circuit_client import CircuitBreakingHttpClient
from mp_commons.kernel.errors import ExternalServiceError
from mp_commons.observability.correlation import CorrelationContext, RequestContext


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _set_correlation(
    correlation_id: str = "test-cid",
    tenant_id: str | None = None,
    user_id: str | None = None,
    trace_id: str | None = None,
) -> RequestContext:
    ctx = RequestContext(
        correlation_id=correlation_id,
        tenant_id=tenant_id,
        user_id=user_id,
        trace_id=trace_id,
    )
    CorrelationContext.set(ctx)
    return ctx


# ---------------------------------------------------------------------------
# §32.1 – Correlation header injection
# ---------------------------------------------------------------------------

class TestCorrelationHeaderInjection:
    """HttpxHttpClient injects correlation headers from CorrelationContext."""

    def teardown_method(self) -> None:
        CorrelationContext.clear()

    @respx.mock
    def test_correlation_id_injected(self) -> None:
        _set_correlation(correlation_id="abc-123")
        route = respx.get("http://svc/ok").mock(return_value=httpx.Response(200))

        async def run() -> None:
            async with HttpxHttpClient() as client:
                await client.get("http://svc/ok")
            sent = route.calls.last.request
            assert sent.headers.get("x-correlation-id") == "abc-123"

        asyncio.run(run())

    @respx.mock
    def test_tenant_and_user_headers_injected(self) -> None:
        _set_correlation(
            correlation_id="cid", tenant_id="tenant-1", user_id="user-42"
        )
        route = respx.get("http://svc/ok").mock(return_value=httpx.Response(200))

        async def run() -> None:
            async with HttpxHttpClient() as client:
                await client.get("http://svc/ok")
            sent = route.calls.last.request
            assert sent.headers.get("x-tenant-id") == "tenant-1"
            assert sent.headers.get("x-user-id") == "user-42"

        asyncio.run(run())

    @respx.mock
    def test_no_correlation_context_no_extra_headers(self) -> None:
        CorrelationContext.clear()
        route = respx.get("http://svc/ok").mock(return_value=httpx.Response(200))

        async def run() -> None:
            async with HttpxHttpClient() as client:
                await client.get("http://svc/ok")
            sent = route.calls.last.request
            assert "x-correlation-id" not in sent.headers

        asyncio.run(run())

    @respx.mock
    def test_explicit_headers_override_correlation(self) -> None:
        """If caller passes explicit headers, they take precedence over correlation."""
        _set_correlation(correlation_id="from-context")
        route = respx.get("http://svc/ok").mock(return_value=httpx.Response(200))

        async def run() -> None:
            async with HttpxHttpClient() as client:
                await client.get(
                    "http://svc/ok", headers={"X-Correlation-ID": "caller-override"}
                )
            sent = route.calls.last.request
            assert sent.headers.get("x-correlation-id") == "caller-override"

        asyncio.run(run())


# ---------------------------------------------------------------------------
# §32.1 – Error mapping
# ---------------------------------------------------------------------------

class TestHttpxErrorMapping:
    """HttpxHttpClient maps httpx errors to domain errors."""

    @respx.mock
    def test_4xx_raises_external_service_error(self) -> None:
        respx.get("http://svc/gone").mock(return_value=httpx.Response(404))

        async def run() -> None:
            async with HttpxHttpClient() as client:
                with pytest.raises(ExternalServiceError) as exc_info:
                    await client.get("http://svc/gone")
            assert exc_info.value.to_dict()["code"] == "external_service_error"

        asyncio.run(run())

    @respx.mock
    def test_5xx_raises_external_service_error(self) -> None:
        respx.get("http://svc/err").mock(return_value=httpx.Response(503))

        async def run() -> None:
            async with HttpxHttpClient() as client:
                with pytest.raises(ExternalServiceError):
                    await client.get("http://svc/err")

        asyncio.run(run())

    @respx.mock
    def test_200_returns_response(self) -> None:
        respx.get("http://svc/ok").mock(return_value=httpx.Response(200, json={"ok": True}))

        async def run() -> None:
            async with HttpxHttpClient() as client:
                resp = await client.get("http://svc/ok")
            assert resp.status_code == 200

        asyncio.run(run())


# ---------------------------------------------------------------------------
# §32.2 – RetryingHttpClient
# ---------------------------------------------------------------------------

class TestRetryingHttpClient:
    """RetryingHttpClient retries on transient 5xx responses."""

    @respx.mock
    def test_retries_on_503_then_succeeds(self) -> None:
        route = respx.get("http://svc/retry").mock(
            side_effect=[
                httpx.Response(503),
                httpx.Response(503),
                httpx.Response(200),
            ]
        )

        async def run() -> None:
            async with RetryingHttpClient(max_attempts=3) as client:
                resp = await client.get("http://svc/retry")
            assert resp.status_code == 200
            assert route.call_count == 3

        asyncio.run(run())

    @respx.mock
    def test_raises_after_max_attempts_exhausted(self) -> None:
        respx.get("http://svc/fail").mock(return_value=httpx.Response(503))

        async def run() -> None:
            async with RetryingHttpClient(max_attempts=2) as client:
                with pytest.raises(Exception):
                    await client.get("http://svc/fail")

        asyncio.run(run())


# ---------------------------------------------------------------------------
# §32.3 – CircuitBreakingHttpClient
# ---------------------------------------------------------------------------

class TestCircuitBreakingHttpClient:
    """CircuitBreakingHttpClient opens the circuit after repeated failures."""

    @respx.mock
    def test_successful_request_passes_through(self) -> None:
        respx.get("http://svc/ok").mock(return_value=httpx.Response(200))

        async def run() -> None:
            async with CircuitBreakingHttpClient() as client:
                resp = await client.get("http://svc/ok")
            assert resp.status_code == 200

        asyncio.run(run())

    @respx.mock
    def test_circuit_opens_after_failure_threshold(self) -> None:
        from mp_commons.resilience.circuit_breaker import CircuitBreakerPolicy
        from mp_commons.resilience.circuit_breaker.errors import CircuitOpenError

        policy = CircuitBreakerPolicy(
            failure_threshold=2,
            success_threshold=1,
            timeout_seconds=60.0,
        )
        respx.get("http://svc/fail").mock(return_value=httpx.Response(503))

        async def run() -> None:
            client = CircuitBreakingHttpClient(cb_policy=policy)
            # Trigger enough failures to open the circuit
            for _ in range(policy.failure_threshold):
                with pytest.raises(ExternalServiceError):
                    await client._request("GET", "http://svc/fail")
            # Circuit should now be OPEN → raises CircuitOpenError
            with pytest.raises(CircuitOpenError):
                await client._request("GET", "http://svc/fail")

        asyncio.run(run())
