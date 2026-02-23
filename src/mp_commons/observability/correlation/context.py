"""Observability – RequestContext, CorrelationContext."""
from __future__ import annotations

import dataclasses
from contextvars import ContextVar
from uuid import uuid4


@dataclasses.dataclass(frozen=True)
class RequestContext:
    """Ambient context for a single request/use-case execution."""
    correlation_id: str
    tenant_id: str | None = None
    user_id: str | None = None
    trace_id: str | None = None
    span_id: str | None = None

    @classmethod
    def new(cls, tenant_id: str | None = None, user_id: str | None = None) -> "RequestContext":
        return cls(correlation_id=str(uuid4()), tenant_id=tenant_id, user_id=user_id)


_CTX_VAR: ContextVar[RequestContext | None] = ContextVar("_mp_request_ctx", default=None)


class CorrelationContext:
    """Ambient correlation context stored in a ``ContextVar``."""

    @staticmethod
    def set(ctx: RequestContext) -> None:
        _CTX_VAR.set(ctx)

    @staticmethod
    def get() -> RequestContext | None:
        return _CTX_VAR.get()

    @staticmethod
    def require() -> RequestContext:
        ctx = _CTX_VAR.get()
        if ctx is None:
            raise RuntimeError("No RequestContext in current context")
        return ctx

    @staticmethod
    def get_or_new() -> RequestContext:
        ctx = _CTX_VAR.get()
        if ctx is None:
            ctx = RequestContext.new()
            _CTX_VAR.set(ctx)
        return ctx

    @staticmethod
    def clear() -> None:
        _CTX_VAR.set(None)

    @staticmethod
    def set_from_headers(headers: dict[str, str]) -> "RequestContext":
        """Extract correlation context from HTTP headers and store it.

        Priority order for correlation ID:
        ``X-Correlation-ID`` → ``X-Request-ID`` → generated UUID.

        W3C ``traceparent`` header (format ``ver-trace_id-parent_id-flags``) is
        parsed to populate :attr:`RequestContext.trace_id`.

        All header names are matched case-insensitively.
        """
        norm: dict[str, str] = {k.lower(): v for k, v in headers.items()}

        correlation_id = (
            norm.get("x-correlation-id")
            or norm.get("x-request-id")
            or str(uuid4())
        )

        # W3C traceparent: 00-{trace-id}-{parent-id}-{flags}
        trace_id: str | None = None
        traceparent = norm.get("traceparent")
        if traceparent:
            parts = traceparent.split("-")
            if len(parts) >= 2 and parts[1]:
                trace_id = parts[1]

        ctx = RequestContext(
            correlation_id=correlation_id,
            trace_id=trace_id,
        )
        _CTX_VAR.set(ctx)
        return ctx


__all__ = ["CorrelationContext", "RequestContext"]
