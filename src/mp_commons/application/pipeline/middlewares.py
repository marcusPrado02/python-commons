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
    """Create an async span wrapping the use case via the Tracer port."""

    def __init__(self, tracer: Any) -> None:
        self._tracer = tracer

    async def __call__(self, request: Any, next_: Next) -> Any:
        name = type(request).__name__
        async with self._tracer.start_async_span(f"use_case.{name}") as span:
            span.set_attribute("use_case.type", name)
            try:
                result = await next_(request)
                span.set_status_ok()
                return result
            except Exception as exc:
                span.record_exception(exc)
                raise


class MetricsMiddleware(Middleware):
    """Record use-case invocation counters and latency histogram."""

    def __init__(self, metrics: Any) -> None:
        self._calls = metrics.counter("use_case.calls", "Use-case invocations")
        self._latency = metrics.histogram("use_case.latency_ms", "Use-case handler latency", "ms")
        self._errors = metrics.counter("use_case.errors", "Use-case handler errors")

    async def __call__(self, request: Any, next_: Next) -> Any:
        import time
        name = type(request).__name__
        labels: dict[str, str] = {"use_case": name}
        start = time.perf_counter()
        try:
            result = await next_(request)
            elapsed = (time.perf_counter() - start) * 1000
            self._calls.add(1.0, labels)
            self._latency.record(elapsed, labels)
            return result
        except Exception:
            self._errors.add(1.0, {**labels, "status": "error"})
            raise


class RetryMiddleware(Middleware):
    """Retry transient failures using the resilience retry module."""

    def __init__(self, max_attempts: int = 3) -> None:
        self._max_attempts = max_attempts

    async def __call__(self, request: Any, next_: Next) -> Any:
        from mp_commons.resilience.retry import RetryPolicy
        policy = RetryPolicy(max_attempts=self._max_attempts)
        return await policy.execute_async(lambda: next_(request))


class IdempotencyMiddleware(Middleware):
    """Skip handler if request was already processed; record result when done."""

    def __init__(self, store: Any) -> None:
        self._store = store

    async def __call__(self, request: Any, next_: Next) -> Any:
        import json
        from mp_commons.kernel.messaging import IdempotencyKey, IdempotencyRecord

        key_value = getattr(request, "idempotency_key", None)
        if key_value is None:
            return await next_(request)

        ikey = IdempotencyKey(client_key=str(key_value), operation=type(request).__name__)
        existing = await self._store.get(ikey)
        if existing is not None and existing.status == "COMPLETED":
            return existing.response

        record = IdempotencyRecord(key=str(ikey))
        await self._store.save(ikey, record)
        result = await next_(request)
        await self._store.complete(ikey, json.dumps({"result": str(result)}).encode())
        return result


class AuthzMiddleware(Middleware):
    """Evaluate access-control policy using SecurityContext + PolicyEngine."""

    def __init__(self, policy_engine: Any, require_auth: bool = True) -> None:
        self._engine = policy_engine
        self._require_auth = require_auth

    async def __call__(self, request: Any, next_: Next) -> Any:
        from mp_commons.kernel.errors import ForbiddenError, UnauthorizedError
        from mp_commons.kernel.security import PolicyContext, PolicyDecision
        from mp_commons.kernel.security.security_context import SecurityContext

        principal = SecurityContext.get_current()
        if principal is None:
            if self._require_auth:
                raise UnauthorizedError("No authenticated principal in context")
            return await next_(request)

        resource = getattr(request, "_resource", type(request).__name__)
        action = getattr(request, "_action", "execute")
        ctx = PolicyContext(principal=principal, resource=resource, action=action)
        decision = await self._engine.evaluate(ctx)
        if decision == PolicyDecision.DENY:
            raise ForbiddenError(f"Access denied: {resource}:{action}")
        return await next_(request)


class CorrelationMiddleware(Middleware):
    """Stamp a ``correlation_id`` on the request context if absent."""

    async def __call__(self, request: Any, next_: Next) -> Any:
        import uuid

        if not getattr(request, "correlation_id", None):
            try:
                object.__setattr__(request, "correlation_id", str(uuid.uuid4()))
            except (AttributeError, TypeError):
                pass
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


class CachingMiddleware(Middleware):
    """Cache Query responses in an async key/value store; bypass for Commands."""

    def __init__(self, cache: Any, default_ttl: int = 300, ttl_map: dict[type, int] | None = None) -> None:
        self._cache = cache
        self._default_ttl = default_ttl
        self._ttl_map: dict[type, int] = ttl_map or {}

    async def __call__(self, request: Any, next_: Next) -> Any:
        import hashlib
        import json
        import pickle

        from mp_commons.application.cqrs.queries import Query

        if not isinstance(request, Query):
            return await next_(request)

        try:
            fields = vars(request) if hasattr(request, "__dict__") else {}
            raw = json.dumps(fields, sort_keys=True, default=str).encode()
        except (TypeError, ValueError):
            raw = repr(request).encode()
        digest = hashlib.sha256(raw).hexdigest()[:16]
        key = f"query:{type(request).__name__}:{digest}"

        cached = await self._cache.get(key)
        if cached is not None:
            return pickle.loads(cached)  # noqa: S301

        result = await next_(request)
        ttl = self._ttl_map.get(type(request), self._default_ttl)
        await self._cache.set(key, pickle.dumps(result), ttl)
        return result


class DeduplicationMiddleware(Middleware):
    """Reject duplicate Command submissions identified by command_id."""

    def __init__(self, store: Any) -> None:
        self._store = store

    async def __call__(self, request: Any, next_: Next) -> Any:
        import json

        from mp_commons.application.cqrs.commands import Command
        from mp_commons.kernel.errors import ConflictError
        from mp_commons.kernel.messaging import IdempotencyKey, IdempotencyRecord

        if not isinstance(request, Command):
            return await next_(request)
        cmd_id = getattr(request, "command_id", None) or getattr(request, "idempotency_key", None)
        if cmd_id is None:
            return await next_(request)

        ikey = IdempotencyKey(client_key=str(cmd_id), operation=type(request).__name__)
        existing = await self._store.get(ikey)
        if existing is not None:
            if existing.status == "COMPLETED":
                return existing.response
            raise ConflictError(f"Duplicate command {type(request).__name__}:{cmd_id}")

        record = IdempotencyRecord(key=str(ikey))
        await self._store.save(ikey, record)
        result = await next_(request)
        await self._store.complete(ikey, json.dumps({"result": str(result)}).encode())
        return result


__all__ = [
    "AuthzMiddleware",
    "CachingMiddleware",
    "CorrelationMiddleware",
    "DeduplicationMiddleware",
    "IdempotencyMiddleware",
    "LoggingMiddleware",
    "MetricsMiddleware",
    "RetryMiddleware",
    "TimeoutMiddleware",
    "TracingMiddleware",
    "UnitOfWorkMiddleware",
    "ValidationMiddleware",
]
