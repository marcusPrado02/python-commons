"""Application pipeline – built-in middleware implementations."""
from __future__ import annotations

from typing import Any

from mp_commons.application.pipeline.middleware import Middleware, Next


class LoggingMiddleware(Middleware):
    """Log request start/end with timing."""

    async def __call__(self, request: Any, next_: Next) -> Any:
        import time
        name = type(request).__name__
        start = time.perf_counter()
        try:
            result = await next_(request)
            duration = (time.perf_counter() - start) * 1000
            try:
                import structlog
                structlog.get_logger().info("use_case.completed", request=name, duration_ms=round(duration, 2))
            except ImportError:
                pass
            return result
        except Exception:
            duration = (time.perf_counter() - start) * 1000
            try:
                import structlog
                structlog.get_logger().error("use_case.failed", request=name, duration_ms=round(duration, 2))
            except ImportError:
                pass
            raise


class TracingMiddleware(Middleware):
    """Create an OTEL span wrapping the use case."""

    def __init__(self, tracer: Any | None = None) -> None:
        self._tracer = tracer

    async def __call__(self, request: Any, next_: Next) -> Any:
        name = type(request).__name__
        if self._tracer is not None:
            with self._tracer.start_as_current_span(f"use_case.{name}"):
                return await next_(request)
        return await next_(request)


class MetricsMiddleware(Middleware):
    """Record use-case invocation counters and latency."""

    def __init__(self, metrics: Any | None = None) -> None:
        self._metrics = metrics

    async def __call__(self, request: Any, next_: Next) -> Any:
        return await next_(request)


class RetryMiddleware(Middleware):
    """Retry transient failures using the resilience retry module."""

    def __init__(self, max_attempts: int = 3) -> None:
        self._max_attempts = max_attempts

    async def __call__(self, request: Any, next_: Next) -> Any:
        from mp_commons.resilience.retry import RetryPolicy
        policy = RetryPolicy(max_attempts=self._max_attempts)
        return await policy.execute_async(lambda: next_(request))


class IdempotencyMiddleware(Middleware):
    """Skip execution if the request has been processed before."""

    def __init__(self, store: Any) -> None:
        self._store = store

    async def __call__(self, request: Any, next_: Next) -> Any:
        from mp_commons.kernel.messaging import IdempotencyKey
        key_value = getattr(request, "idempotency_key", None)
        if key_value is None:
            return await next_(request)
        key = IdempotencyKey(client_key=str(key_value), operation=type(request).__name__)
        existing = await self._store.get(key)
        if existing is not None and existing.status == "COMPLETED":
            return existing.response
        return await next_(request)


class AuthzMiddleware(Middleware):
    """Evaluate access-control policy before executing the use case."""

    def __init__(self, policy_engine: Any) -> None:
        self._engine = policy_engine

    async def __call__(self, request: Any, next_: Next) -> Any:
        from mp_commons.kernel.security import PolicyContext, PolicyDecision
        principal = getattr(request, "_principal", None)
        resource = getattr(request, "_resource", type(request).__name__)
        action = getattr(request, "_action", "execute")
        if principal is not None:
            ctx = PolicyContext(principal=principal, resource=resource, action=action)
            decision = await self._engine.evaluate(ctx)
            if decision == PolicyDecision.DENY:
                from mp_commons.kernel.errors import ForbiddenError
                raise ForbiddenError(f"Access denied to {resource}:{action}")
        return await next_(request)


class ValidationMiddleware(Middleware):
    """Call ``request.validate()`` if it exists."""

    async def __call__(self, request: Any, next_: Next) -> Any:
        validate = getattr(request, "validate", None)
        if callable(validate):
            validate()
        return await next_(request)


class UnitOfWorkMiddleware(Middleware):
    """Open/commit (or rollback) a UoW around the handler."""

    def __init__(self, uow_factory: Any) -> None:
        self._factory = uow_factory

    async def __call__(self, request: Any, next_: Next) -> Any:
        async with self._factory() as uow:
            request._uow = uow  # noqa: SLF001
            return await next_(request)


class TimeoutMiddleware(Middleware):
    """Raise ``TimeoutError`` if the use case exceeds *timeout_seconds*."""

    def __init__(self, timeout_seconds: float) -> None:
        self._timeout = timeout_seconds

    async def __call__(self, request: Any, next_: Next) -> Any:
        import asyncio
        from mp_commons.kernel.errors import TimeoutError as AppTimeoutError
        try:
            return await asyncio.wait_for(next_(request), timeout=self._timeout)
        except TimeoutError as exc:
            raise AppTimeoutError(f"Use case timed out after {self._timeout}s") from exc


__all__ = [
    "AuthzMiddleware",
    "IdempotencyMiddleware",
    "LoggingMiddleware",
    "MetricsMiddleware",
    "RetryMiddleware",
    "TimeoutMiddleware",
    "TracingMiddleware",
    "UnitOfWorkMiddleware",
    "ValidationMiddleware",
]
