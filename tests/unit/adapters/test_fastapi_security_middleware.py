"""Unit tests for IncomingWebhookMiddleware and SecurityHeadersMiddleware (S-02, S-04)."""
from __future__ import annotations

import hashlib
import hmac
import json
import sys
import types
from unittest.mock import AsyncMock, MagicMock

import pytest

# Stub fastapi/starlette so tests run without the real library
for _mod_name in ("fastapi", "starlette", "starlette.types"):
    if _mod_name not in sys.modules:
        sys.modules[_mod_name] = types.ModuleType(_mod_name)

from mp_commons.adapters.fastapi.middleware import (  # noqa: E402
    FastAPIIncomingWebhookMiddleware,
    FastAPISecurityHeadersMiddleware,
)


# ---------------------------------------------------------------------------
# ASGI test helpers
# ---------------------------------------------------------------------------


def _make_http_scope(path: str = "/webhooks/github", headers: list | None = None) -> dict:
    return {
        "type": "http",
        "path": path,
        "raw_path": path.encode(),
        "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or [])],
        "client": ("127.0.0.1", 12345),
    }


def _make_receive(body: bytes = b"") -> AsyncMock:
    receive = AsyncMock()
    receive.return_value = {"type": "http.request", "body": body, "more_body": False}
    return receive


class _ResponseCollector:
    """Captures ASGI send messages."""

    def __init__(self) -> None:
        self.messages: list[dict] = []

    async def __call__(self, message: dict) -> None:
        self.messages.append(message)

    @property
    def status(self) -> int:
        return self.messages[0]["status"]

    @property
    def response_headers(self) -> dict[str, str]:
        return {k.decode(): v.decode() for k, v in self.messages[0].get("headers", [])}


def _make_signature(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


# ---------------------------------------------------------------------------
# FastAPIIncomingWebhookMiddleware
# ---------------------------------------------------------------------------


class TestFastAPIIncomingWebhookMiddleware:
    _SECRET = "super-secret"

    def _make_middleware(self, inner_app: MagicMock | None = None) -> FastAPIIncomingWebhookMiddleware:
        app = inner_app or AsyncMock()
        return FastAPIIncomingWebhookMiddleware(app, secret=self._SECRET)

    async def test_valid_signature_passes(self):
        body = b'{"event": "push"}'
        sig = _make_signature(self._SECRET, body)
        inner = AsyncMock()
        mw = self._make_middleware(inner)
        scope = _make_http_scope(headers=[("x-hub-signature-256", sig)])
        receive = _make_receive(body)
        collector = _ResponseCollector()
        await mw(scope, receive, collector)
        inner.assert_called_once()

    async def test_invalid_signature_returns_401(self):
        body = b'{"event": "push"}'
        inner = AsyncMock()
        mw = self._make_middleware(inner)
        scope = _make_http_scope(headers=[("x-hub-signature-256", "sha256=deadbeef")])
        receive = _make_receive(body)
        collector = _ResponseCollector()
        await mw(scope, receive, collector)
        inner.assert_not_called()
        assert collector.status == 401

    async def test_missing_signature_returns_401(self):
        body = b'{"event": "push"}'
        inner = AsyncMock()
        mw = self._make_middleware(inner)
        scope = _make_http_scope()  # no sig header
        receive = _make_receive(body)
        collector = _ResponseCollector()
        await mw(scope, receive, collector)
        inner.assert_not_called()
        assert collector.status == 401

    async def test_non_webhook_path_skips_verification(self):
        inner = AsyncMock()
        mw = self._make_middleware(inner)
        scope = _make_http_scope(path="/api/users")  # outside /webhooks
        receive = _make_receive(b"body")
        collector = _ResponseCollector()
        await mw(scope, receive, collector)
        inner.assert_called_once()

    async def test_non_http_scope_passes_through(self):
        inner = AsyncMock()
        mw = self._make_middleware(inner)
        scope = {"type": "lifespan"}
        receive = AsyncMock()
        send = AsyncMock()
        await mw(scope, receive, send)
        inner.assert_called_once()

    async def test_body_replayed_to_inner_app(self):
        """The inner app must be able to read the full body after verification."""
        body = b"payload data"
        sig = _make_signature(self._SECRET, body)
        received_bodies: list[bytes] = []

        async def inner_app(scope, receive, send):
            msg = await receive()
            received_bodies.append(msg.get("body", b""))

        mw = FastAPIIncomingWebhookMiddleware(inner_app, secret=self._SECRET)
        scope = _make_http_scope(headers=[("x-hub-signature-256", sig)])
        receive = _make_receive(body)
        await mw(scope, receive, _ResponseCollector())

        assert received_bodies == [body]

    async def test_custom_path_prefix(self):
        body = b"data"
        sig = _make_signature(self._SECRET, body)
        inner = AsyncMock()
        mw = FastAPIIncomingWebhookMiddleware(inner, secret=self._SECRET, path_prefix="/hooks")
        scope = _make_http_scope(path="/hooks/stripe", headers=[("x-hub-signature-256", sig)])
        await mw(scope, _make_receive(body), _ResponseCollector())
        inner.assert_called_once()


# ---------------------------------------------------------------------------
# FastAPISecurityHeadersMiddleware
# ---------------------------------------------------------------------------


class TestFastAPISecurityHeadersMiddleware:
    async def _run(self, mw: FastAPISecurityHeadersMiddleware) -> dict[str, str]:
        inner_sent: list[dict] = []

        async def inner(scope, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})

        scope = _make_http_scope(path="/")
        collector = _ResponseCollector()
        await mw(scope, _make_receive(), collector)
        return collector.response_headers

    async def _run_headers(self, mw: FastAPISecurityHeadersMiddleware) -> dict[str, str]:
        async def inner(scope, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})

        mw.app = inner
        scope = _make_http_scope(path="/")
        collector = _ResponseCollector()
        await mw(scope, _make_receive(), collector)
        return collector.response_headers

    async def test_default_headers_added(self):
        inner = AsyncMock()
        mw = FastAPISecurityHeadersMiddleware(inner)
        headers = await self._run_headers(mw)

        assert "x-frame-options" in headers
        assert headers["x-frame-options"] == "DENY"
        assert "x-content-type-options" in headers
        assert headers["x-content-type-options"] == "nosniff"
        assert "strict-transport-security" in headers
        assert "content-security-policy" in headers

    async def test_custom_csp(self):
        custom_csp = "default-src 'none'"
        inner = AsyncMock()
        mw = FastAPISecurityHeadersMiddleware(inner, content_security_policy=custom_csp)
        headers = await self._run_headers(mw)
        assert headers["content-security-policy"] == custom_csp

    async def test_header_disabled_when_none(self):
        inner = AsyncMock()
        mw = FastAPISecurityHeadersMiddleware(inner, x_frame_options=None)
        headers = await self._run_headers(mw)
        assert "x-frame-options" not in headers

    async def test_non_http_scope_not_modified(self):
        inner = AsyncMock()
        mw = FastAPISecurityHeadersMiddleware(inner)
        scope = {"type": "lifespan"}
        receive = AsyncMock()
        send = AsyncMock()
        await mw(scope, receive, send)
        inner.assert_called_once()
        send.assert_not_called()
