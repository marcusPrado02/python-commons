"""gRPC server-side interceptors.

Provides three ``grpc.aio.ServerInterceptor`` implementations:

* :class:`CorrelationIdServerInterceptor` — extracts ``x-correlation-id``
  from incoming metadata and sets :class:`~mp_commons.observability.correlation.context.CorrelationContext`.
* :class:`AuthServerInterceptor` — validates the ``authorization: Bearer <token>``
  metadata entry using a :class:`~mp_commons.security.jwt.JwtDecoder` and aborts
  with ``UNAUTHENTICATED`` on failure.
* :class:`MetricsServerInterceptor` — records per-RPC request count and
  latency histogram via a :class:`~mp_commons.observability.metrics.MetricsRegistry`.

Requires ``grpcio>=1.60``.
"""

from __future__ import annotations

from collections.abc import Callable
import time
from typing import Any


def _require_grpc() -> Any:
    try:
        import grpc  # type: ignore[import-untyped]

        return grpc
    except ImportError as exc:
        raise ImportError(
            "grpcio is required for the gRPC adapter. Install it with: pip install 'grpcio>=1.60'"
        ) from exc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _metadata_value(metadata: Any, key: str) -> str | None:
    """Return the first value for *key* in *metadata* or ``None``."""
    if metadata is None:
        return None
    for k, v in metadata:
        if k.lower() == key.lower():
            return v if isinstance(v, str) else v.decode("utf-8", errors="replace")
    return None


# ---------------------------------------------------------------------------
# CorrelationIdServerInterceptor
# ---------------------------------------------------------------------------


class CorrelationIdServerInterceptor:
    """Extract ``x-correlation-id`` from incoming gRPC metadata and set it as
    the ambient :class:`~mp_commons.observability.correlation.context.CorrelationContext`.

    If the header is absent a new correlation ID is generated automatically so
    every RPC always has a correlation ID in scope.

    Usage::

        server = grpc.aio.server(interceptors=[CorrelationIdServerInterceptor()])
    """

    _METADATA_KEY = "x-correlation-id"

    async def intercept_service_async(
        self,
        continuation: Callable[..., Any],
        handler_call_details: Any,
    ) -> Any:
        return _CorrelationIdWrapper(await continuation(handler_call_details))

    # grpc.aio uses intercept_service for async interceptors
    async def intercept_service(
        self,
        continuation: Callable[..., Any],
        handler_call_details: Any,
    ) -> Any:
        return _CorrelationIdWrapper(await continuation(handler_call_details))


class _CorrelationIdWrapper:
    """Wraps an RPC handler to inject correlation context before calling it."""

    _METADATA_KEY = "x-correlation-id"

    def __init__(self, handler: Any) -> None:
        self._handler = handler

    def _inject(self, servicer_context: Any) -> None:
        from uuid import uuid4

        from mp_commons.observability.correlation.context import (
            CorrelationContext,
            RequestContext,
        )

        correlation_id = _metadata_value(servicer_context.invocation_metadata(), self._METADATA_KEY)
        ctx = RequestContext(correlation_id=correlation_id or str(uuid4()))
        CorrelationContext.set(ctx)

    async def unary_unary(self, request: Any, context: Any) -> Any:
        self._inject(context)
        return await self._handler.unary_unary(request, context)

    async def unary_stream(self, request: Any, context: Any) -> Any:
        self._inject(context)
        async for item in self._handler.unary_stream(request, context):
            yield item

    async def stream_unary(self, request_iterator: Any, context: Any) -> Any:
        self._inject(context)
        return await self._handler.stream_unary(request_iterator, context)

    async def stream_stream(self, request_iterator: Any, context: Any) -> Any:
        self._inject(context)
        async for item in self._handler.stream_stream(request_iterator, context):
            yield item

    def __getattr__(self, name: str) -> Any:
        return getattr(self._handler, name)


# ---------------------------------------------------------------------------
# AuthServerInterceptor
# ---------------------------------------------------------------------------


class AuthServerInterceptor:
    """Validate ``authorization: Bearer <token>`` metadata before allowing an
    RPC to proceed.

    Uses a :class:`~mp_commons.security.jwt.JwtDecoder` to verify the token.
    On failure, the RPC is aborted with ``UNAUTHENTICATED``.

    Parameters
    ----------
    decoder:
        A :class:`~mp_commons.security.jwt.JwtDecoder` instance.
    secret_or_key:
        The secret or public key passed to ``decoder.decode``.
    algorithms:
        Token signing algorithms accepted (default: ``["HS256"]``).
    audience:
        Expected ``aud`` claim value; ``None`` skips audience validation.
    public_methods:
        Set of fully-qualified RPC method names that bypass auth, e.g.
        ``{"/mypackage.MyService/HealthCheck"}``.

    Usage::

        auth = AuthServerInterceptor(decoder=JwtDecoder(), secret_or_key="s3cr3t")
        server = grpc.aio.server(interceptors=[auth])
    """

    _METADATA_KEY = "authorization"

    def __init__(
        self,
        decoder: Any,
        secret_or_key: str | bytes,
        *,
        algorithms: list[str] | None = None,
        audience: str | list[str] | None = None,
        public_methods: set[str] | None = None,
    ) -> None:
        self._decoder = decoder
        self._secret_or_key = secret_or_key
        self._algorithms = algorithms or ["HS256"]
        self._audience = audience
        self._public_methods: set[str] = public_methods or set()

    async def intercept_service(
        self,
        continuation: Callable[..., Any],
        handler_call_details: Any,
    ) -> Any:
        method = getattr(handler_call_details, "method", "")
        if method in self._public_methods:
            return await continuation(handler_call_details)
        return _AuthWrapper(
            await continuation(handler_call_details),
            decoder=self._decoder,
            secret_or_key=self._secret_or_key,
            algorithms=self._algorithms,
            audience=self._audience,
        )


class _AuthWrapper:
    _METADATA_KEY = "authorization"

    def __init__(
        self,
        handler: Any,
        *,
        decoder: Any,
        secret_or_key: str | bytes,
        algorithms: list[str],
        audience: Any,
    ) -> None:
        self._handler = handler
        self._decoder = decoder
        self._secret_or_key = secret_or_key
        self._algorithms = algorithms
        self._audience = audience

    def _validate(self, context: Any) -> bool:
        """Return ``True`` if the token is valid; abort the RPC otherwise."""
        from mp_commons.security.jwt.decoder import JwtValidationError

        grpc = _require_grpc()
        header = _metadata_value(context.invocation_metadata(), self._METADATA_KEY)
        if not header or not header.lower().startswith("bearer "):
            context.set_code(grpc.StatusCode.UNAUTHENTICATED)
            context.set_details("Missing or malformed authorization header")
            return False
        token = header[len("bearer ") :].strip()
        try:
            self._decoder.decode(
                token,
                self._secret_or_key,
                algorithms=self._algorithms,
                audience=self._audience,
            )
        except JwtValidationError as exc:
            context.set_code(grpc.StatusCode.UNAUTHENTICATED)
            context.set_details(str(exc))
            return False
        return True

    async def unary_unary(self, request: Any, context: Any) -> Any:
        if not self._validate(context):
            return None
        return await self._handler.unary_unary(request, context)

    async def unary_stream(self, request: Any, context: Any) -> Any:
        if not self._validate(context):
            return
        async for item in self._handler.unary_stream(request, context):
            yield item

    async def stream_unary(self, request_iterator: Any, context: Any) -> Any:
        if not self._validate(context):
            return None
        return await self._handler.stream_unary(request_iterator, context)

    async def stream_stream(self, request_iterator: Any, context: Any) -> Any:
        if not self._validate(context):
            return
        async for item in self._handler.stream_stream(request_iterator, context):
            yield item

    def __getattr__(self, name: str) -> Any:
        return getattr(self._handler, name)


# ---------------------------------------------------------------------------
# MetricsServerInterceptor
# ---------------------------------------------------------------------------


class MetricsServerInterceptor:
    """Record per-RPC request count and latency histogram via a
    :class:`~mp_commons.observability.metrics.MetricsRegistry`.

    Metrics emitted (labels include ``method`` and ``status``):

    * ``grpc_server_requests_total`` — counter
    * ``grpc_server_request_duration_seconds`` — histogram

    Parameters
    ----------
    registry:
        A :class:`~mp_commons.observability.metrics.MetricsRegistry` instance.

    Usage::

        metrics = MetricsServerInterceptor(registry=my_registry)
        server = grpc.aio.server(interceptors=[metrics])
    """

    _COUNTER = "grpc_server_requests_total"
    _HISTOGRAM = "grpc_server_request_duration_seconds"

    def __init__(self, registry: Any) -> None:
        self._registry = registry

    async def intercept_service(
        self,
        continuation: Callable[..., Any],
        handler_call_details: Any,
    ) -> Any:
        method = getattr(handler_call_details, "method", "unknown")
        return _MetricsWrapper(
            await continuation(handler_call_details),
            registry=self._registry,
            method=method,
        )


class _MetricsWrapper:
    def __init__(self, handler: Any, *, registry: Any, method: str) -> None:
        self._handler = handler
        self._registry = registry
        self._method = method

    def _record(self, status: str, elapsed: float) -> None:
        labels = {"method": self._method, "status": status}
        try:
            self._registry.increment(MetricsServerInterceptor._COUNTER, labels=labels)
            self._registry.histogram(MetricsServerInterceptor._HISTOGRAM, elapsed, labels=labels)
        except Exception:
            pass  # never let metrics recording break the RPC

    async def unary_unary(self, request: Any, context: Any) -> Any:
        start = time.monotonic()
        status = "OK"
        try:
            result = await self._handler.unary_unary(request, context)
            return result
        except Exception:
            status = "ERROR"
            raise
        finally:
            self._record(status, time.monotonic() - start)

    async def unary_stream(self, request: Any, context: Any) -> Any:
        start = time.monotonic()
        status = "OK"
        try:
            async for item in self._handler.unary_stream(request, context):
                yield item
        except Exception:
            status = "ERROR"
            raise
        finally:
            self._record(status, time.monotonic() - start)

    async def stream_unary(self, request_iterator: Any, context: Any) -> Any:
        start = time.monotonic()
        status = "OK"
        try:
            result = await self._handler.stream_unary(request_iterator, context)
            return result
        except Exception:
            status = "ERROR"
            raise
        finally:
            self._record(status, time.monotonic() - start)

    async def stream_stream(self, request_iterator: Any, context: Any) -> Any:
        start = time.monotonic()
        status = "OK"
        try:
            async for item in self._handler.stream_stream(request_iterator, context):
                yield item
        except Exception:
            status = "ERROR"
            raise
        finally:
            self._record(status, time.monotonic() - start)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._handler, name)


__all__ = [
    "AuthServerInterceptor",
    "CorrelationIdServerInterceptor",
    "MetricsServerInterceptor",
]
