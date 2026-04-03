"""Unit tests for the gRPC adapter (§51)."""

from __future__ import annotations

import asyncio
import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Stub the grpc package so tests run without the real library
# ---------------------------------------------------------------------------

_grpc_mod = types.ModuleType("grpc")
_grpc_aio_mod = types.ModuleType("grpc.aio")
_grpc_mod.aio = _grpc_aio_mod  # type: ignore[attr-defined]

# Stub credentials
_grpc_mod.ssl_channel_credentials = MagicMock(return_value="ssl_creds")  # type: ignore[attr-defined]
_grpc_aio_mod.insecure_channel = MagicMock(return_value="insecure_channel")  # type: ignore[attr-defined]
_grpc_aio_mod.secure_channel = MagicMock(return_value="secure_channel")  # type: ignore[attr-defined]


class _RpcError(Exception):
    pass


_grpc_mod.RpcError = _RpcError  # type: ignore[attr-defined]
_grpc_mod.StatusCode = MagicMock()  # type: ignore[attr-defined]
_grpc_mod.StatusCode.UNAVAILABLE = "UNAVAILABLE"  # type: ignore[attr-defined]
sys.modules.setdefault("grpc", _grpc_mod)
sys.modules.setdefault("grpc.aio", _grpc_aio_mod)

from mp_commons.adapters.grpc.channel import (
    CorrelationIdClientInterceptor,
    GrpcChannelFactory,
    GrpcHealthStatus,
    RetryClientInterceptor,
)

# ---------------------------------------------------------------------------
# GrpcChannelFactory
# ---------------------------------------------------------------------------


def test_channel_factory_insecure():
    _grpc_aio_mod.insecure_channel.reset_mock()
    factory = GrpcChannelFactory()
    factory.create("localhost:50051")
    _grpc_aio_mod.insecure_channel.assert_called_once_with(
        "localhost:50051", options=[], interceptors=[]
    )


def test_channel_factory_tls():
    _grpc_aio_mod.secure_channel.reset_mock()
    factory = GrpcChannelFactory()
    factory.create("secure.host:443", tls=True)
    _grpc_aio_mod.secure_channel.assert_called_once()
    args = _grpc_aio_mod.secure_channel.call_args[0]
    assert args[0] == "secure.host:443"
    assert args[1] == "ssl_creds"


def test_channel_factory_custom_credentials():
    _grpc_aio_mod.secure_channel.reset_mock()
    creds = MagicMock()
    factory = GrpcChannelFactory()
    factory.create("host:443", credentials=creds)
    _grpc_aio_mod.secure_channel.assert_called_once()
    args = _grpc_aio_mod.secure_channel.call_args[0]
    assert args[1] is creds


# ---------------------------------------------------------------------------
# CorrelationIdClientInterceptor
# ---------------------------------------------------------------------------


def test_correlation_interceptor_injects_header():
    interceptor = CorrelationIdClientInterceptor()

    # Stub out CorrelationContext
    with patch.object(
        interceptor,
        "_get_correlation_id",
        return_value="corr-123",
    ):
        details = MagicMock()
        details.metadata = []
        continuation = AsyncMock(return_value="response")

        result = asyncio.run(interceptor.intercept_unary_unary(continuation, details, "request"))

        assert result == "response"
        continuation.assert_called_once()
        injected_details = continuation.call_args[0][0]
        metadata = injected_details.metadata
        assert any(k == "x-correlation-id" and v == "corr-123" for k, v in metadata)


def test_correlation_interceptor_skips_when_no_id():
    interceptor = CorrelationIdClientInterceptor()

    with patch.object(interceptor, "_get_correlation_id", return_value=None):
        details = MagicMock()
        details.metadata = []
        continuation = AsyncMock(return_value="response")

        asyncio.run(interceptor.intercept_unary_unary(continuation, details, "request"))
        # called with original details (no x-correlation-id injected)
        continuation.assert_called_once_with(details, "request")


# ---------------------------------------------------------------------------
# RetryClientInterceptor
# ---------------------------------------------------------------------------


def test_retry_interceptor_succeeds_on_first_try():
    policy = MagicMock()
    policy.execute_async = AsyncMock(return_value="ok")
    interceptor = RetryClientInterceptor(policy)
    details = MagicMock()
    continuation = AsyncMock(return_value="ok")

    result = asyncio.run(interceptor.intercept_unary_unary(continuation, details, "req"))
    assert result == "ok"
    policy.execute_async.assert_called_once()


def test_retry_interceptor_propagates_exception():
    policy = MagicMock()
    policy.execute_async = AsyncMock(side_effect=RuntimeError("unavailable"))
    interceptor = RetryClientInterceptor(policy)
    details = MagicMock()
    continuation = AsyncMock()

    with pytest.raises(RuntimeError, match="unavailable"):
        asyncio.run(interceptor.intercept_unary_unary(continuation, details, "req"))


# ---------------------------------------------------------------------------
# GrpcHealthStatus enum
# ---------------------------------------------------------------------------


def test_health_status_values():
    assert GrpcHealthStatus.SERVING == "SERVING"
    assert GrpcHealthStatus.NOT_SERVING == "NOT_SERVING"
    assert GrpcHealthStatus.UNKNOWN == "UNKNOWN"
