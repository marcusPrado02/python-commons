"""gRPC adapter — channel factory, correlation-id interceptor, retry interceptor,
and health checker.

Requires ``grpcio>=1.60``.  All classes raise :class:`ImportError` with a clear
message when the library is absent.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Callable


def _require_grpc() -> Any:
    try:
        import grpc  # type: ignore[import-untyped]

        return grpc
    except ImportError as exc:
        raise ImportError(
            "grpcio is required for the gRPC adapter. "
            "Install it with: pip install 'grpcio>=1.60'"
        ) from exc


def _require_grpc_aio() -> Any:
    grpc = _require_grpc()
    return grpc.aio


# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------


class GrpcHealthStatus(str, Enum):
    SERVING = "SERVING"
    NOT_SERVING = "NOT_SERVING"
    UNKNOWN = "UNKNOWN"
    SERVICE_UNKNOWN = "SERVICE_UNKNOWN"


# ---------------------------------------------------------------------------
# Channel factory
# ---------------------------------------------------------------------------


class GrpcChannelFactory:
    """Create :class:`grpc.aio.Channel` instances with optional TLS.

    Usage::

        factory = GrpcChannelFactory()
        channel = factory.create("localhost:50051")
        stub = MyServiceStub(channel)
    """

    def create(
        self,
        target: str,
        *,
        tls: bool = False,
        credentials: Any = None,
        options: list[tuple[str, Any]] | None = None,
        interceptors: list[Any] | None = None,
    ) -> Any:
        """Return an async gRPC channel.

        Parameters
        ----------
        target:
            ``host:port`` of the gRPC server.
        tls:
            Use :func:`grpc.ssl_channel_credentials` with default roots when
            *credentials* is *None*.
        credentials:
            Explicit channel credentials; overrides *tls* flag.
        options:
            Extra gRPC channel options passed to the underlying create call.
        interceptors:
            Client-side interceptors to attach.
        """
        grpc = _require_grpc()
        aio = grpc.aio
        opts = options or []
        iceptors = interceptors or []
        if credentials is not None:
            return aio.secure_channel(target, credentials, options=opts, interceptors=iceptors)
        if tls:
            creds = grpc.ssl_channel_credentials()
            return aio.secure_channel(target, creds, options=opts, interceptors=iceptors)
        return aio.insecure_channel(target, options=opts, interceptors=iceptors)


# ---------------------------------------------------------------------------
# Correlation-ID interceptor
# ---------------------------------------------------------------------------


class CorrelationIdClientInterceptor:
    """gRPC :class:`grpc.aio.UnaryUnaryClientInterceptor` that injects the
    current correlation-id from :class:`CorrelationContext` as
    ``x-correlation-id`` metadata.
    """

    _METADATA_KEY = "x-correlation-id"

    def _get_correlation_id(self) -> str | None:
        try:
            from mp_commons.observability.correlation.context import CorrelationContext

            ctx = CorrelationContext.get()
            if ctx is not None:
                return ctx.correlation_id
        except Exception:
            pass
        return None

    def _inject(self, client_call_details: Any) -> Any:
        """Return a copy of *client_call_details* with the x-correlation-id header."""
        grpc = _require_grpc()

        correlation_id = self._get_correlation_id()
        if not correlation_id:
            return client_call_details

        # client_call_details is immutable; patch via a simple namespace
        import copy

        details = copy.copy(client_call_details)
        existing = list(getattr(details, "metadata", None) or [])
        existing.append((self._METADATA_KEY, correlation_id))
        object.__setattr__(details, "metadata", existing) if hasattr(details, "__setattr__") else setattr(details, "metadata", existing)
        return details

    # Depending on grpc version the method signature differs slightly.
    async def intercept_unary_unary(self, continuation: Any, client_call_details: Any, request: Any) -> Any:
        return await continuation(self._inject(client_call_details), request)

    async def intercept_unary_stream(self, continuation: Any, client_call_details: Any, request: Any) -> Any:
        return await continuation(self._inject(client_call_details), request)


# ---------------------------------------------------------------------------
# Retry interceptor
# ---------------------------------------------------------------------------


class RetryClientInterceptor:
    """gRPC client interceptor that retries on ``UNAVAILABLE`` status using a
    :class:`~mp_commons.resilience.retry.policy.RetryPolicy`.

    Parameters
    ----------
    retry_policy:
        The :class:`~mp_commons.resilience.retry.policy.RetryPolicy` to apply.
    """

    def __init__(self, retry_policy: Any) -> None:
        self._policy = retry_policy

    async def intercept_unary_unary(self, continuation: Any, client_call_details: Any, request: Any) -> Any:
        grpc = _require_grpc()

        async def _call() -> Any:
            response = await continuation(client_call_details, request)
            # Await the call to get the actual response
            return response

        try:
            return await self._policy.execute_async(_call)
        except Exception as exc:
            # Re-raise any exception that exhausted retries
            raise


# ---------------------------------------------------------------------------
# Health checker
# ---------------------------------------------------------------------------


class GrpcHealthChecker:
    """Check a remote service's health using the standard gRPC health protocol.

    Parameters
    ----------
    channel:
        An open :class:`grpc.aio.Channel`.
    """

    def __init__(self, channel: Any) -> None:
        self._channel = channel

    async def check(self, service: str = "") -> GrpcHealthStatus:
        """Return the health status of *service*.

        Parameters
        ----------
        service:
            Service name as registered in the health server.  Empty string
            checks the overall server health.
        """
        grpc = _require_grpc()
        try:
            from grpc_health.v1 import health_pb2, health_pb2_grpc  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ImportError(
                "grpcio-health-checking is required for GrpcHealthChecker. "
                "Install it with: pip install 'grpcio-health-checking>=1.60'"
            ) from exc

        stub = health_pb2_grpc.HealthStub(self._channel)
        try:
            request = health_pb2.HealthCheckRequest(service=service)
            response = await stub.Check(request)
            status_val = response.status
            # Map proto enum to our enum
            _MAP = {
                health_pb2.HealthCheckResponse.SERVING: GrpcHealthStatus.SERVING,
                health_pb2.HealthCheckResponse.NOT_SERVING: GrpcHealthStatus.NOT_SERVING,
                health_pb2.HealthCheckResponse.SERVICE_UNKNOWN: GrpcHealthStatus.SERVICE_UNKNOWN,
            }
            return _MAP.get(status_val, GrpcHealthStatus.UNKNOWN)
        except grpc.RpcError:
            return GrpcHealthStatus.UNKNOWN


__all__ = [
    "CorrelationIdClientInterceptor",
    "GrpcChannelFactory",
    "GrpcHealthChecker",
    "GrpcHealthStatus",
    "RetryClientInterceptor",
]
