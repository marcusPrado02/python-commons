"""Unit / integration tests for §26 – FastAPI adapter."""
from __future__ import annotations

import asyncio
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Imported at module level so FastAPI can resolve string-form annotations
# (from __future__ import annotations makes all hints lazy strings, and
# FastAPI resolves them against the defining module's globals).
from mp_commons.adapters.fastapi.deps import FastAPIPaginationDep  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_app() -> FastAPI:
    return FastAPI()


# ---------------------------------------------------------------------------
# §26.1  FastAPICorrelationIdMiddleware
# ---------------------------------------------------------------------------

class TestFastAPICorrelationIdMiddleware:
    """§26.1 – Correlation ID injection."""

    def _app(self) -> FastAPI:
        from mp_commons.adapters.fastapi import FastAPICorrelationIdMiddleware

        app = FastAPI()
        app.add_middleware(FastAPICorrelationIdMiddleware)

        @app.get("/ping")
        async def ping() -> dict[str, str]:
            return {"pong": "true"}

        return app

    def test_generated_correlation_id_returned_in_header(self) -> None:
        client = TestClient(self._app())
        resp = client.get("/ping")
        assert resp.status_code == 200
        assert "x-correlation-id" in resp.headers

    def test_client_supplied_id_echoed_back(self) -> None:
        client = TestClient(self._app())
        resp = client.get("/ping", headers={"X-Correlation-ID": "my-req-123"})
        assert resp.headers["x-correlation-id"] == "my-req-123"

    def test_fallback_to_x_request_id(self) -> None:
        client = TestClient(self._app())
        resp = client.get("/ping", headers={"X-Request-ID": "req-fallback"})
        assert resp.headers["x-correlation-id"] == "req-fallback"

    def test_traceparent_extraction(self) -> None:
        traceparent = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
        client = TestClient(self._app())
        resp = client.get("/ping", headers={"traceparent": traceparent})
        # expects the trace-id segment
        assert resp.headers["x-correlation-id"] == "4bf92f3577b34da6a3ce929d0e0e4736"

    def test_correlation_id_set_in_context(self) -> None:
        from mp_commons.adapters.fastapi import FastAPICorrelationIdMiddleware
        from mp_commons.observability.correlation import CorrelationContext

        app = FastAPI()
        app.add_middleware(FastAPICorrelationIdMiddleware)
        captured: list[str] = []

        @app.get("/capture")
        async def capture() -> dict[str, str]:
            ctx = CorrelationContext.get()
            if ctx:
                captured.append(ctx.correlation_id)
            return {"ok": "1"}

        client = TestClient(app)
        client.get("/capture", headers={"X-Correlation-ID": "ctx-id-test"})
        assert captured == ["ctx-id-test"]


# ---------------------------------------------------------------------------
# §26.2  FastAPITenantMiddleware
# ---------------------------------------------------------------------------

class TestFastAPITenantMiddleware:
    """§26.2 – Tenant context from header."""

    def test_tenant_header_sets_context(self) -> None:
        from mp_commons.adapters.fastapi import FastAPITenantMiddleware
        from mp_commons.kernel.ddd.tenant import TenantContext

        app = FastAPI()
        app.add_middleware(FastAPITenantMiddleware)
        captured: list[Any] = []

        @app.get("/t")
        async def endpoint() -> dict[str, str]:
            captured.append(TenantContext.get())
            return {"ok": "1"}

        client = TestClient(app)
        client.get("/t", headers={"X-Tenant-ID": "tenant-abc"})
        assert captured and str(captured[0]) == "tenant-abc"

    def test_missing_header_no_tenant(self) -> None:
        from mp_commons.adapters.fastapi import FastAPITenantMiddleware

        app = FastAPI()
        app.add_middleware(FastAPITenantMiddleware)

        @app.get("/t")
        async def endpoint() -> dict[str, str]:
            return {"ok": "1"}

        client = TestClient(app)
        resp = client.get("/t")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# §26.3  FastAPISecurityMiddleware
# ---------------------------------------------------------------------------

class TestFastAPISecurityMiddleware:
    """§26.3 – Bearer token extraction + optional auth."""

    def _make_verifier(self, principal: Any):
        async def verify(token: str) -> Any:
            if token == "good-token":
                return principal
            return None
        return verify

    def test_no_verifier_passes_through(self) -> None:
        from mp_commons.adapters.fastapi import FastAPISecurityMiddleware

        app = FastAPI()
        app.add_middleware(FastAPISecurityMiddleware, require_auth=False)

        @app.get("/sec")
        async def endpoint() -> dict[str, str]:
            return {"ok": "1"}

        client = TestClient(app)
        resp = client.get("/sec")
        assert resp.status_code == 200

    def test_require_auth_without_token_returns_401(self) -> None:
        from mp_commons.adapters.fastapi import FastAPISecurityMiddleware

        app = FastAPI()
        app.add_middleware(FastAPISecurityMiddleware, require_auth=True)

        @app.get("/sec")
        async def endpoint() -> dict[str, str]:
            return {"ok": "1"}

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/sec")
        assert resp.status_code == 401

    def test_valid_token_sets_security_context(self) -> None:
        from mp_commons.adapters.fastapi import FastAPISecurityMiddleware
        from mp_commons.kernel.security.security_context import SecurityContext

        class FakePrincipal:
            id = "user-1"

        principal = FakePrincipal()
        app = FastAPI()
        app.add_middleware(
            FastAPISecurityMiddleware,
            verifier=self._make_verifier(principal),
            require_auth=True,
        )
        captured: list[Any] = []

        @app.get("/sec")
        async def endpoint() -> dict[str, str]:
            captured.append(SecurityContext.get_current())
            return {"ok": "1"}

        client = TestClient(app)
        resp = client.get("/sec", headers={"Authorization": "Bearer good-token"})
        assert resp.status_code == 200
        assert captured and captured[0] is principal

    def test_invalid_token_with_require_auth_returns_401(self) -> None:
        from mp_commons.adapters.fastapi import FastAPISecurityMiddleware

        app = FastAPI()
        app.add_middleware(
            FastAPISecurityMiddleware,
            verifier=self._make_verifier(None),
            require_auth=True,
        )

        @app.get("/sec")
        async def endpoint() -> dict[str, str]:
            return {"ok": "1"}

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/sec", headers={"Authorization": "Bearer bad-token"})
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# §26.4  FastAPIExceptionMapper
# ---------------------------------------------------------------------------

class TestFastAPIExceptionMapper:
    """§26.4 – Error → HTTP status code and body shape."""

    def _app_with_errors(self) -> FastAPI:
        from mp_commons.adapters.fastapi import FastAPICorrelationIdMiddleware, FastAPIExceptionMapper
        from mp_commons.kernel.errors import (
            ConflictError, DomainError, ForbiddenError, InfrastructureError,
            NotFoundError, RateLimitError, TimeoutError, UnauthorizedError, ValidationError,
        )

        app = FastAPI()
        app.add_middleware(FastAPICorrelationIdMiddleware)
        FastAPIExceptionMapper().register(app)

        @app.get("/raise/{kind}")
        async def raise_error(kind: str) -> dict[str, str]:
            mapping = {
                "validation": ValidationError("bad field"),
                "notfound": NotFoundError("Widget not found"),
                "conflict": ConflictError("Already exists"),
                "unauthorized": UnauthorizedError("Token expired"),
                "forbidden": ForbiddenError("No permission"),
                "ratelimit": RateLimitError("Too fast"),
                "timeout": TimeoutError("Downstream timeout"),
                "domain": DomainError("Rule broken"),
                "infrastructure": InfrastructureError("DB unreachable"),
            }
            raise mapping[kind]

        return app

    @pytest.mark.parametrize("kind,expected_status", [
        ("validation", 400),
        ("notfound", 404),
        ("conflict", 409),
        ("unauthorized", 401),
        ("forbidden", 403),
        ("ratelimit", 429),
        ("timeout", 504),
        ("domain", 422),
        ("infrastructure", 503),
    ])
    def test_error_status_codes(self, kind: str, expected_status: int) -> None:
        client = TestClient(self._app_with_errors(), raise_server_exceptions=False)
        resp = client.get(f"/raise/{kind}")
        assert resp.status_code == expected_status

    def test_error_body_has_code_and_message(self) -> None:
        client = TestClient(self._app_with_errors(), raise_server_exceptions=False)
        resp = client.get("/raise/notfound")
        body = resp.json()
        assert "code" in body
        assert "message" in body

    def test_error_body_has_correlation_id(self) -> None:
        client = TestClient(self._app_with_errors(), raise_server_exceptions=False)
        resp = client.get("/raise/notfound", headers={"X-Correlation-ID": "corr-123"})
        body = resp.json()
        assert body.get("correlation_id") == "corr-123"


# ---------------------------------------------------------------------------
# §26.5  FastAPIHealthRouter
# ---------------------------------------------------------------------------

class TestFastAPIHealthRouter:
    """§26.5 – Health endpoints."""

    def _app(self, readiness_checks=None) -> FastAPI:
        from mp_commons.adapters.fastapi import FastAPIHealthRouter

        app = FastAPI()
        app.include_router(FastAPIHealthRouter(readiness_checks=readiness_checks))
        return app

    def test_liveness_returns_200(self) -> None:
        client = TestClient(self._app())
        resp = client.get("/health/live")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_readiness_no_checks_returns_200(self) -> None:
        client = TestClient(self._app())
        resp = client.get("/health/ready")
        assert resp.status_code == 200

    def test_readiness_all_pass_returns_200(self) -> None:
        async def check_ok() -> bool:
            return True

        client = TestClient(self._app(readiness_checks=[check_ok]))
        resp = client.get("/health/ready")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_readiness_failing_check_returns_503(self) -> None:
        async def check_fail() -> bool:
            return False

        client = TestClient(self._app(readiness_checks=[check_fail]))
        resp = client.get("/health/ready")
        assert resp.status_code == 503
        assert resp.json()["status"] == "degraded"

    def test_readiness_exception_in_check_returns_503(self) -> None:
        async def check_raises() -> bool:
            raise RuntimeError("db offline")

        client = TestClient(self._app(readiness_checks=[check_raises]))
        resp = client.get("/health/ready")
        assert resp.status_code == 503

    def test_readiness_mixed_checks(self) -> None:
        async def ok() -> bool:
            return True

        async def fail() -> bool:
            return False

        client = TestClient(self._app(readiness_checks=[ok, fail]))
        resp = client.get("/health/ready")
        assert resp.status_code == 503


# ---------------------------------------------------------------------------
# §26.8  FastAPIPaginationDep
# ---------------------------------------------------------------------------

class TestFastAPIPaginationDep:
    """§26.8 – Pagination dependency injection."""

    def _app(self) -> FastAPI:
        from mp_commons.adapters.fastapi.deps import FastAPIPaginationDep

        app = FastAPI()

        @app.get("/items")
        async def list_items(pagination: FastAPIPaginationDep) -> dict[str, Any]:  # type: ignore[valid-type]
            return {
                "page": pagination.page,
                "size": pagination.size,
                "sorts": list(pagination.sorts),
            }

        return app

    def test_defaults(self) -> None:
        client = TestClient(self._app())
        resp = client.get("/items")
        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 1
        assert data["size"] == 20
        assert data["sorts"] == []

    def test_custom_page_and_size(self) -> None:
        client = TestClient(self._app())
        resp = client.get("/items?page=3&size=50")
        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 3
        assert data["size"] == 50

    def test_sort_asc(self) -> None:
        client = TestClient(self._app())
        resp = client.get("/items?sort_by=name&sort_dir=asc")
        data = resp.json()
        assert data["sorts"] == ["name"]

    def test_sort_desc(self) -> None:
        client = TestClient(self._app())
        resp = client.get("/items?sort_by=created_at&sort_dir=desc")
        data = resp.json()
        assert data["sorts"] == ["-created_at"]

    def test_page_must_be_ge_1(self) -> None:
        client = TestClient(self._app(), raise_server_exceptions=False)
        resp = client.get("/items?page=0")
        assert resp.status_code == 422

    def test_size_must_be_ge_1(self) -> None:
        client = TestClient(self._app(), raise_server_exceptions=False)
        resp = client.get("/items?size=0")
        assert resp.status_code == 422

    def test_size_must_be_le_1000(self) -> None:
        client = TestClient(self._app(), raise_server_exceptions=False)
        resp = client.get("/items?size=1001")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# §26.9  FastAPIRateLimitMiddleware
# ---------------------------------------------------------------------------

class TestFastAPIRateLimitMiddleware:
    """§26.9 – Rate-limit middleware."""

    def _app(self, allowed: bool, retry_after: float = 5.0) -> FastAPI:
        from mp_commons.adapters.fastapi import FastAPIRateLimitMiddleware

        class FakeResult:
            def __init__(self) -> None:
                self.allowed = allowed
                self.retry_after_seconds = retry_after

        class FakeLimiter:
            async def check(self, quota: Any, identifier: str) -> FakeResult:
                return FakeResult()

        class FakeQuota:
            pass

        app = FastAPI()
        app.add_middleware(
            FastAPIRateLimitMiddleware,
            limiter=FakeLimiter(),
            quota=FakeQuota(),
        )

        @app.get("/data")
        async def data() -> dict[str, str]:
            return {"ok": "1"}

        return app

    def test_allowed_request_passes_through(self) -> None:
        client = TestClient(self._app(allowed=True))
        resp = client.get("/data")
        assert resp.status_code == 200

    def test_denied_request_returns_429(self) -> None:
        client = TestClient(self._app(allowed=False, retry_after=10.0), raise_server_exceptions=False)
        resp = client.get("/data")
        assert resp.status_code == 429

    def test_retry_after_header_present(self) -> None:
        client = TestClient(self._app(allowed=False, retry_after=10.0), raise_server_exceptions=False)
        resp = client.get("/data")
        assert "retry-after" in resp.headers
        assert int(resp.headers["retry-after"]) >= 10

    def test_denied_body_has_error_code(self) -> None:
        client = TestClient(self._app(allowed=False), raise_server_exceptions=False)
        resp = client.get("/data")
        body = resp.json()
        assert body["code"] == "rate_limit_exceeded"


# ---------------------------------------------------------------------------
# §26.10  error_responses helper
# ---------------------------------------------------------------------------

class TestErrorResponses:
    """§26.10 – OpenAPI extra helpers."""

    def test_returns_dict_with_requested_codes(self) -> None:
        from mp_commons.adapters.fastapi.deps import error_responses
        result = error_responses(400, 404, 422)
        assert set(result.keys()) == {"400", "404", "422"}

    def test_each_entry_has_description_and_content(self) -> None:
        from mp_commons.adapters.fastapi.deps import error_responses
        result = error_responses(404)
        entry = result["404"]
        assert "description" in entry
        assert "content" in entry

    def test_schema_contains_code_and_message(self) -> None:
        from mp_commons.adapters.fastapi.deps import error_responses
        result = error_responses(400)
        schema = result["400"]["content"]["application/json"]["schema"]  # type: ignore[index]
        assert "code" in schema["properties"]
        assert "message" in schema["properties"]

    def test_example_has_correlation_id(self) -> None:
        from mp_commons.adapters.fastapi.deps import error_responses
        result = error_responses(422)
        example = result["422"]["content"]["application/json"]["example"]  # type: ignore[index]
        assert "correlation_id" in example

    def test_unknown_code_handled_gracefully(self) -> None:
        from mp_commons.adapters.fastapi.deps import error_responses
        result = error_responses(418)
        assert "418" in result
