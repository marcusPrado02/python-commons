"""Unit tests for gRPC server-side interceptors (G-01, G-02, G-03)."""
from __future__ import annotations

import asyncio
import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Stub optional heavy dependencies so tests run in a minimal environment
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Stub grpc so tests run without the real library
# ---------------------------------------------------------------------------

_grpc_mod = types.ModuleType("grpc")
_grpc_aio_mod = types.ModuleType("grpc.aio")
_grpc_mod.aio = _grpc_aio_mod  # type: ignore[attr-defined]


class _StatusCode:
    UNAUTHENTICATED = "UNAUTHENTICATED"
    OK = "OK"


_grpc_mod.StatusCode = _StatusCode  # type: ignore[attr-defined]
sys.modules.setdefault("grpc", _grpc_mod)
sys.modules.setdefault("grpc.aio", _grpc_aio_mod)

from mp_commons.adapters.grpc.server import (  # noqa: E402
    AuthServerInterceptor,
    CorrelationIdServerInterceptor,
    MetricsServerInterceptor,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_context(metadata: list[tuple[str, str]] | None = None) -> MagicMock:
    ctx = MagicMock()
    ctx.invocation_metadata.return_value = metadata or []
    return ctx


def _make_handler(return_value: Any = "rpc_result") -> MagicMock:
    handler = MagicMock()
    handler.unary_unary = AsyncMock(return_value=return_value)
    return handler


from typing import Any


# ---------------------------------------------------------------------------
# CorrelationIdServerInterceptor
# ---------------------------------------------------------------------------


class TestCorrelationIdServerInterceptor:
    def test_sets_correlation_id_from_metadata(self):
        interceptor = CorrelationIdServerInterceptor()
        handler = _make_handler("ok")
        context = _make_context([("x-correlation-id", "abc-123")])

        captured: list[Any] = []

        from mp_commons.observability.correlation.context import CorrelationContext

        original_set = CorrelationContext.set

        def _capture(ctx):
            captured.append(ctx)
            original_set(ctx)

        with patch.object(CorrelationContext, "set", side_effect=_capture):
            wrapper = asyncio.run(_make_continuation_result(interceptor, handler))
            asyncio.run(wrapper.unary_unary("request", context))

        assert len(captured) == 1
        assert captured[0].correlation_id == "abc-123"

    def test_generates_correlation_id_when_absent(self):
        interceptor = CorrelationIdServerInterceptor()
        handler = _make_handler("ok")
        context = _make_context([])

        captured: list[Any] = []

        from mp_commons.observability.correlation.context import CorrelationContext

        original_set = CorrelationContext.set

        def _capture(ctx):
            captured.append(ctx)
            original_set(ctx)

        with patch.object(CorrelationContext, "set", side_effect=_capture):
            wrapper = asyncio.run(_make_continuation_result(interceptor, handler))
            asyncio.run(wrapper.unary_unary("request", context))

        assert len(captured) == 1
        assert len(captured[0].correlation_id) == 36  # UUID length

    def test_proxies_other_attributes_to_handler(self):
        interceptor = CorrelationIdServerInterceptor()
        handler = MagicMock()
        handler.some_attr = "value"
        wrapper = asyncio.run(_make_continuation_result(interceptor, handler))
        assert wrapper.some_attr == "value"


async def _make_continuation_result(interceptor: Any, handler: Any) -> Any:
    details = MagicMock()

    async def continuation(_details: Any) -> Any:
        return handler

    return await interceptor.intercept_service(continuation, details)


# ---------------------------------------------------------------------------
# AuthServerInterceptor
# ---------------------------------------------------------------------------


class TestAuthServerInterceptor:
    def _make_interceptor(self, public_methods: set[str] | None = None) -> AuthServerInterceptor:
        decoder = MagicMock()
        decoder.decode.return_value = MagicMock(sub="user-1")
        return AuthServerInterceptor(
            decoder=decoder,
            secret_or_key="secret",
            public_methods=public_methods,
        )

    def test_valid_token_allows_rpc(self):
        interceptor = self._make_interceptor()
        handler = _make_handler("result")
        context = _make_context([("authorization", "Bearer valid_token")])

        wrapper = asyncio.run(_make_continuation_result(interceptor, handler))
        result = asyncio.run(wrapper.unary_unary("req", context))
        assert result == "result"

    def test_missing_auth_header_aborts(self):
        interceptor = self._make_interceptor()
        handler = _make_handler("result")
        context = _make_context([])

        wrapper = asyncio.run(_make_continuation_result(interceptor, handler))
        result = asyncio.run(wrapper.unary_unary("req", context))

        context.set_code.assert_called_once_with(_StatusCode.UNAUTHENTICATED)
        assert result is None

    def test_invalid_token_aborts(self):
        from mp_commons.security.jwt.decoder import JwtValidationError

        decoder = MagicMock()
        decoder.decode.side_effect = JwtValidationError("expired")
        interceptor = AuthServerInterceptor(decoder=decoder, secret_or_key="s")
        handler = _make_handler("result")
        context = _make_context([("authorization", "Bearer bad_token")])

        wrapper = asyncio.run(_make_continuation_result(interceptor, handler))
        result = asyncio.run(wrapper.unary_unary("req", context))

        context.set_code.assert_called_once_with(_StatusCode.UNAUTHENTICATED)
        context.set_details.assert_called_once_with("expired")
        assert result is None

    def test_public_method_bypasses_auth(self):
        interceptor = self._make_interceptor(public_methods={"/pkg.Svc/Health"})
        handler = _make_handler("pong")
        context = _make_context([])

        details = MagicMock()
        details.method = "/pkg.Svc/Health"

        async def run():
            async def cont(_d):
                return handler

            wrapper = await interceptor.intercept_service(cont, details)
            return await wrapper.unary_unary("req", context)

        result = asyncio.run(run())
        assert result == "pong"
        context.set_code.assert_not_called()

    def test_malformed_auth_header_aborts(self):
        interceptor = self._make_interceptor()
        handler = _make_handler("result")
        context = _make_context([("authorization", "Basic dXNlcjpwYXNz")])

        wrapper = asyncio.run(_make_continuation_result(interceptor, handler))
        result = asyncio.run(wrapper.unary_unary("req", context))

        context.set_code.assert_called_once_with(_StatusCode.UNAUTHENTICATED)
        assert result is None


# ---------------------------------------------------------------------------
# MetricsServerInterceptor
# ---------------------------------------------------------------------------


class TestMetricsServerInterceptor:
    def _make_interceptor(self) -> tuple[MetricsServerInterceptor, MagicMock]:
        registry = MagicMock()
        return MetricsServerInterceptor(registry=registry), registry

    def test_records_counter_and_histogram_on_success(self):
        interceptor, registry = self._make_interceptor()
        handler = _make_handler("ok")
        context = _make_context()

        details = MagicMock()
        details.method = "/pkg.Svc/Greet"

        async def run():
            async def cont(_d):
                return handler

            wrapper = await interceptor.intercept_service(cont, details)
            return await wrapper.unary_unary("req", context)

        asyncio.run(run())

        registry.increment.assert_called_once()
        call_kwargs = registry.increment.call_args
        assert call_kwargs[0][0] == "grpc_server_requests_total"
        assert call_kwargs[1]["labels"]["method"] == "/pkg.Svc/Greet"
        assert call_kwargs[1]["labels"]["status"] == "OK"

        registry.histogram.assert_called_once()

    def test_records_error_status_on_exception(self):
        interceptor, registry = self._make_interceptor()
        handler = MagicMock()
        handler.unary_unary = AsyncMock(side_effect=RuntimeError("boom"))
        context = _make_context()

        details = MagicMock()
        details.method = "/pkg.Svc/Fail"

        async def run():
            async def cont(_d):
                return handler

            wrapper = await interceptor.intercept_service(cont, details)
            with pytest.raises(RuntimeError, match="boom"):
                await wrapper.unary_unary("req", context)

        asyncio.run(run())

        call_kwargs = registry.increment.call_args
        assert call_kwargs[1]["labels"]["status"] == "ERROR"

    def test_metrics_failure_does_not_break_rpc(self):
        """If the registry raises, the RPC must still succeed."""
        interceptor, registry = self._make_interceptor()
        registry.increment.side_effect = RuntimeError("metrics down")
        handler = _make_handler("ok")
        context = _make_context()

        details = MagicMock()
        details.method = "/pkg.Svc/Safe"

        async def run():
            async def cont(_d):
                return handler

            wrapper = await interceptor.intercept_service(cont, details)
            return await wrapper.unary_unary("req", context)

        result = asyncio.run(run())
        assert result == "ok"
