"""FastAPI adapter – ASGI middleware implementations.

§26.1  FastAPICorrelationIdMiddleware
§26.2  FastAPITenantMiddleware
§26.3  FastAPISecurityMiddleware
§26.6  FastAPIMetricsMiddleware
§26.9  FastAPIRateLimitMiddleware
"""
from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any, Callable, Awaitable

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Receive, Scope, Send


def _require_fastapi() -> None:
    try:
        import fastapi  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "Install 'mp-commons[fastapi]' to use the FastAPI adapter"
        ) from exc


# ---------------------------------------------------------------------------
# §26.1 – Correlation-ID middleware
# ---------------------------------------------------------------------------

class FastAPICorrelationIdMiddleware:
    """Extract correlation ID from request headers, propagate to response.

    Header resolution order:
    1. ``X-Correlation-ID``
    2. ``X-Request-ID``
    3. ``traceparent`` (W3C trace-context, extracts trace-id segment)
    4. Generated UUID v4
    """

    def __init__(
        self,
        app: "ASGIApp",
        header_name: str = "X-Correlation-ID",
        fallback_headers: tuple[str, ...] = ("X-Request-ID", "traceparent"),
    ) -> None:
        _require_fastapi()
        self.app = app
        self._response_header = header_name.lower().encode()
        self._request_headers: list[bytes] = [
            header_name.lower().encode(),
            *[h.lower().encode() for h in fallback_headers],
        ]

    async def __call__(self, scope: "Scope", receive: "Receive", send: "Send") -> None:
        from uuid import uuid4

        from mp_commons.observability.correlation import CorrelationContext, RequestContext

        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))

        correlation_id: str | None = None
        for header in self._request_headers:
            value = headers.get(header, b"").decode().strip()
            if value:
                # W3C traceparent: 00-<trace-id>-<span-id>-<flags>
                if header == b"traceparent" and "-" in value:
                    parts = value.split("-")
                    if len(parts) >= 2:
                        correlation_id = parts[1]
                else:
                    correlation_id = value
                break

        correlation_id = correlation_id or str(uuid4())
        ctx = RequestContext(correlation_id=correlation_id)
        CorrelationContext.set(ctx)

        try:
            import structlog
            structlog.contextvars.bind_contextvars(correlation_id=correlation_id)
        except ImportError:
            pass

        response_header = self._response_header
        encoded_id = correlation_id.encode()

        async def send_with_header(message: Any) -> None:
            if message["type"] == "http.response.start":
                headers_list: list[tuple[bytes, bytes]] = list(message.get("headers", []))
                headers_list.append((response_header, encoded_id))
                message = {**message, "headers": headers_list}
            await send(message)

        await self.app(scope, receive, send_with_header)


# ---------------------------------------------------------------------------
# §26.2 – Tenant middleware
# ---------------------------------------------------------------------------

class FastAPITenantMiddleware:
    """Extract ``X-Tenant-ID`` header and set :class:`TenantContext`."""

    def __init__(self, app: "ASGIApp", header_name: str = "X-Tenant-ID") -> None:
        _require_fastapi()
        self.app = app
        self._header = header_name.lower().encode()

    async def __call__(self, scope: "Scope", receive: "Receive", send: "Send") -> None:
        if scope["type"] == "http":
            from mp_commons.kernel.ddd.tenant import TenantContext
            from mp_commons.kernel.types.ids import TenantId

            headers = dict(scope.get("headers", []))
            tenant_raw = headers.get(self._header, b"").decode().strip()
            if tenant_raw:
                TenantContext.set(TenantId(tenant_raw))

        await self.app(scope, receive, send)


# ---------------------------------------------------------------------------
# §26.3 – Security (JWT / OIDC) middleware
# ---------------------------------------------------------------------------

class FastAPISecurityMiddleware:
    """Extract a Bearer JWT, verify it, and populate :class:`SecurityContext`.

    Parameters
    ----------
    app:
        The inner ASGI application.
    verifier:
        Any callable ``async (token: str) -> Principal | None``.  Pass
        your ``OIDCTokenVerifier.verify`` here.  If ``None`` the middleware
        is a no-op (useful in tests).
    require_auth:
        When ``True`` (default) requests without a valid token receive 401.
        When ``False`` the request proceeds with no principal.
    """

    def __init__(
        self,
        app: "ASGIApp",
        verifier: Callable[[str], Awaitable[Any]] | None = None,
        require_auth: bool = False,
    ) -> None:
        _require_fastapi()
        self.app = app
        self._verifier = verifier
        self._require_auth = require_auth

    async def __call__(self, scope: "Scope", receive: "Receive", send: "Send") -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        auth_value = headers.get(b"authorization", b"").decode().strip()

        principal = None
        if auth_value.lower().startswith("bearer "):
            token = auth_value[7:].strip()
            if self._verifier is not None and token:
                try:
                    principal = await self._verifier(token)
                except Exception:  # noqa: BLE001
                    principal = None

        if principal is not None:
            from mp_commons.kernel.security.security_context import SecurityContext
            SecurityContext.set_current(principal)
        elif self._require_auth:
            import json
            body = json.dumps({"code": "unauthorized", "message": "Missing or invalid credentials"}).encode()
            await send({"type": "http.response.start", "status": 401, "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ]})
            await send({"type": "http.response.body", "body": body})
            return

        await self.app(scope, receive, send)


# ---------------------------------------------------------------------------
# §26.6 – Metrics middleware
# ---------------------------------------------------------------------------

class FastAPIMetricsMiddleware:
    """Record per-route request counts and latency histograms."""

    def __init__(self, app: "ASGIApp", metrics: Any) -> None:
        _require_fastapi()
        self.app = app
        self._requests = metrics.counter(
            "http.requests",
            "Total HTTP requests",
        )
        self._latency = metrics.histogram(
            "http.latency_ms",
            "HTTP request latency",
            "ms",
        )
        self._errors = metrics.counter(
            "http.errors",
            "HTTP 5xx responses",
        )

    async def __call__(self, scope: "Scope", receive: "Receive", send: "Send") -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "GET")
        path = scope.get("path", "")
        labels: dict[str, str] = {"method": method, "path": path}
        start = time.perf_counter()
        status_code: list[int] = [200]

        async def send_capturing(message: Any) -> None:
            if message["type"] == "http.response.start":
                status_code[0] = message.get("status", 200)
            await send(message)

        try:
            await self.app(scope, receive, send_capturing)
        finally:
            elapsed = (time.perf_counter() - start) * 1000
            status_labels = {**labels, "status": str(status_code[0])}
            self._requests.add(1.0, status_labels)
            self._latency.record(elapsed, labels)
            if status_code[0] >= 500:
                self._errors.add(1.0, labels)


# ---------------------------------------------------------------------------
# §26.9 – Rate-limit middleware
# ---------------------------------------------------------------------------

class FastAPIRateLimitMiddleware:
    """Enforce a rate limit via the :class:`RateLimiter` port.

    Returns HTTP 429 with a ``Retry-After`` header when the limit is exceeded.
    """

    def __init__(
        self,
        app: "ASGIApp",
        limiter: Any,
        quota: Any,
        identifier_fn: Callable[["Scope"], str] | None = None,
    ) -> None:
        _require_fastapi()
        self.app = app
        self._limiter = limiter
        self._quota = quota
        self._identifier_fn = identifier_fn or _default_identifier

    async def __call__(self, scope: "Scope", receive: "Receive", send: "Send") -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        import json

        identifier = self._identifier_fn(scope)
        result = await self._limiter.check(self._quota, identifier)

        if not result.allowed:
            retry_after = str(int(result.retry_after_seconds) + 1)
            body = json.dumps({
                "code": "rate_limit_exceeded",
                "message": f"Rate limit exceeded. Retry after {retry_after}s.",
            }).encode()
            headers = [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
                (b"retry-after", retry_after.encode()),
            ]
            await send({"type": "http.response.start", "status": 429, "headers": headers})
            await send({"type": "http.response.body", "body": body})
            return

        await self.app(scope, receive, send)


def _default_identifier(scope: Any) -> str:
    """Extract client IP from ASGI scope as rate-limit identifier."""
    client = scope.get("client")
    if client and isinstance(client, (tuple, list)) and client:
        return str(client[0])
    return "unknown"


# ---------------------------------------------------------------------------
# §26.1 companion – combined correlation + tenant context middleware
# ---------------------------------------------------------------------------

class FastAPIRequestContextMiddleware:
    """Populate ``RequestContext`` from both correlation and tenant headers.

    Convenience wrapper that sets both
    :class:`~mp_commons.observability.correlation.CorrelationContext` and
    the tenant-id in one middleware instead of stacking two.
    """

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
                correlation_id=(
                    headers.get(self._correlation_h, b"").decode().strip() or str(uuid4())
                ),
                tenant_id=headers.get(self._tenant_h, b"").decode().strip() or None,
            )
            CorrelationContext.set(ctx)

        await self.app(scope, receive, send)


__all__ = [
    "FastAPICorrelationIdMiddleware",
    "FastAPIMetricsMiddleware",
    "FastAPIRateLimitMiddleware",
    "FastAPIRequestContextMiddleware",
    "FastAPISecurityMiddleware",
    "FastAPITenantMiddleware",
]
