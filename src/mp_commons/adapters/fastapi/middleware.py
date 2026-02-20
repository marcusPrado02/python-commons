"""FastAPI adapter – correlation and request context middleware."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Receive, Scope, Send


def _require_fastapi() -> None:
    try:
        import fastapi  # noqa: F401
    except ImportError as exc:
        raise ImportError("Install 'mp-commons[fastapi]' to use the FastAPI adapter") from exc


class FastAPICorrelationIdMiddleware:
    """Inject/propagate a correlation ID through X-Correlation-ID header."""

    def __init__(self, app: "ASGIApp", header_name: str = "X-Correlation-ID") -> None:
        _require_fastapi()
        self.app = app
        self._header = header_name.lower().encode()

    async def __call__(self, scope: "Scope", receive: "Receive", send: "Send") -> None:
        from uuid import uuid4
        from mp_commons.observability.correlation import CorrelationContext, RequestContext

        if scope["type"] in ("http", "websocket"):
            headers = dict(scope.get("headers", []))
            correlation_id = headers.get(self._header, b"").decode() or str(uuid4())
            ctx = RequestContext(correlation_id=correlation_id)
            CorrelationContext.set(ctx)
            try:
                import structlog
                structlog.contextvars.bind_contextvars(correlation_id=correlation_id)
            except ImportError:
                pass

        await self.app(scope, receive, send)


class FastAPIRequestContextMiddleware:
    """Populate ``RequestContext`` from request headers."""

    def __init__(
        self,
        app: "ASGIApp",
        correlation_header: str = "X-Correlation-ID",
        tenant_header: str = "X-Tenant-ID",
    ) -> None:
        _require_fastapi()
        self.app = app
        self._correlation_h = correlation_header.lower().encode()
        self._tenant_h = tenant_header.lower().encode()

    async def __call__(self, scope: "Scope", receive: "Receive", send: "Send") -> None:
        from uuid import uuid4
        from mp_commons.observability.correlation import CorrelationContext, RequestContext

        if scope["type"] == "http":
            headers = dict(scope.get("headers", []))
            ctx = RequestContext(
                correlation_id=(headers.get(self._correlation_h, b"").decode() or str(uuid4())),
                tenant_id=headers.get(self._tenant_h, b"").decode() or None,
            )
            CorrelationContext.set(ctx)

        await self.app(scope, receive, send)


__all__ = ["FastAPICorrelationIdMiddleware", "FastAPIRequestContextMiddleware"]
