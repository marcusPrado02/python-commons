"""Unit tests for kernel security — §8."""

from __future__ import annotations

import asyncio
import contextvars

import pytest

from mp_commons.kernel.security import (
    DEFAULT_SENSITIVE_FIELDS,
    CryptoProvider,
    PIIRedactor,
    PasswordHasher,
    Permission,
    PolicyContext,
    PolicyDecision,
    PolicyEngine,
    Principal,
    RegexPIIRedactor,
    Role,
    SecurityContext,
)
from mp_commons.kernel.errors import UnauthorizedError


# ---------------------------------------------------------------------------
# Principal (8.1)
# ---------------------------------------------------------------------------


class TestPrincipal:
    def _principal(self, **kw) -> Principal:
        return Principal(subject="user-1", **kw)

    def test_frozen(self) -> None:
        p = self._principal()
        with pytest.raises((AttributeError, TypeError)):
            p.subject = "other"  # type: ignore[misc]

    def test_has_role_true(self) -> None:
        p = self._principal(roles=frozenset({Role("ADMIN")}))
        assert p.has_role("ADMIN") is True
        assert p.has_role(Role("ADMIN")) is True

    def test_has_role_false(self) -> None:
        p = self._principal(roles=frozenset())
        assert p.has_role("ADMIN") is False

    def test_has_permission_true(self) -> None:
        p = self._principal(permissions=frozenset({Permission("orders:write")}))
        assert p.has_permission("orders:write") is True

    def test_has_permission_false(self) -> None:
        p = self._principal()
        assert p.has_permission("orders:read") is False

    def test_claims_default_empty(self) -> None:
        p = self._principal()
        assert p.claims == {}

    def test_service_account_flag(self) -> None:
        p = self._principal(is_service_account=True)
        assert p.is_service_account is True


# ---------------------------------------------------------------------------
# PolicyDecision enum (8.2)
# ---------------------------------------------------------------------------


class TestPolicyDecision:
    def test_allow_deny_distinct(self) -> None:
        assert PolicyDecision.ALLOW != PolicyDecision.DENY

    def test_string_values(self) -> None:
        assert PolicyDecision.ALLOW == "ALLOW"
        assert PolicyDecision.DENY == "DENY"


# ---------------------------------------------------------------------------
# PolicyEngine stub (8.3)
# ---------------------------------------------------------------------------


class AllowEngine:
    async def evaluate(self, context: PolicyContext) -> PolicyDecision:
        return PolicyDecision.ALLOW


class DenyEngine:
    async def evaluate(self, context: PolicyContext) -> PolicyDecision:
        return PolicyDecision.DENY


class TestPolicyEngine:
    def test_allow_engine(self) -> None:
        ctx = PolicyContext(
            principal=Principal(subject="u"),
            resource="orders",
            action="read",
        )
        result = asyncio.run(AllowEngine().evaluate(ctx))
        assert result == PolicyDecision.ALLOW

    def test_deny_engine(self) -> None:
        ctx = PolicyContext(
            principal=Principal(subject="u"),
            resource="reports",
            action="delete",
        )
        result = asyncio.run(DenyEngine().evaluate(ctx))
        assert result == PolicyDecision.DENY

    def test_policy_context_frozen(self) -> None:
        ctx = PolicyContext(
            principal=Principal(subject="u"),
            resource="r",
            action="a",
        )
        with pytest.raises((AttributeError, TypeError)):
            ctx.resource = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# PIIRedactor — RegexPIIRedactor (8.5)
# ---------------------------------------------------------------------------


class TestRegexPIIRedactor:
    def _redactor(self) -> RegexPIIRedactor:
        return RegexPIIRedactor()

    def test_sensitive_field_masked(self) -> None:
        r = self._redactor()
        result = r.redact({"password": "supersecret", "name": "Alice"})
        assert result["password"] == "***"
        assert result["name"] == "Alice"

    def test_api_key_masked(self) -> None:
        r = self._redactor()
        assert r.redact({"api_key": "abc123"})["api_key"] == "***"

    def test_email_in_value_is_redacted(self) -> None:
        r = self._redactor()
        result = r.redact({"message": "Contact user@example.com for help"})
        assert "user@example.com" not in result["message"]
        assert "[EMAIL]" in result["message"]

    def test_cpf_in_value_is_redacted(self) -> None:
        r = self._redactor()
        result = r.redact({"doc": "CPF: 123.456.789-09"})
        assert "123.456.789-09" not in result["doc"]
        assert "[CPF]" in result["doc"]

    def test_nested_dict_redacted(self) -> None:
        r = self._redactor()
        result = r.redact({"user": {"password": "secret", "name": "Bob"}})
        assert result["user"]["password"] == "***"
        assert result["user"]["name"] == "Bob"

    def test_non_string_value_preserved(self) -> None:
        r = self._redactor()
        result = r.redact({"count": 42, "active": True})
        assert result["count"] == 42
        assert result["active"] is True

    def test_empty_dict(self) -> None:
        r = self._redactor()
        assert r.redact({}) == {}

    def test_custom_sensitive_fields(self) -> None:
        r = RegexPIIRedactor(sensitive_fields=frozenset({"my_secret"}))
        result = r.redact({"my_secret": "val", "password": "plain"})
        assert result["my_secret"] == "***"
        # "password" not in custom set, so not masked
        assert result["password"] == "plain"

    def test_default_sensitive_fields_coverage(self) -> None:
        assert "password" in DEFAULT_SENSITIVE_FIELDS
        assert "token" in DEFAULT_SENSITIVE_FIELDS
        assert "cpf" in DEFAULT_SENSITIVE_FIELDS


# ---------------------------------------------------------------------------
# SecurityContext (8.6)
# ---------------------------------------------------------------------------


class TestSecurityContext:
    def setup_method(self) -> None:
        SecurityContext.clear()

    def teardown_method(self) -> None:
        SecurityContext.clear()

    def test_get_current_returns_none_when_empty(self) -> None:
        assert SecurityContext.get_current() is None

    def test_set_and_get(self) -> None:
        p = Principal(subject="user-42")
        SecurityContext.set_current(p)
        assert SecurityContext.get_current() is p

    def test_clear_removes_principal(self) -> None:
        SecurityContext.set_current(Principal(subject="u"))
        SecurityContext.clear()
        assert SecurityContext.get_current() is None

    def test_require_raises_when_empty(self) -> None:
        with pytest.raises(UnauthorizedError):
            SecurityContext.require()

    def test_require_returns_principal(self) -> None:
        p = Principal(subject="u")
        SecurityContext.set_current(p)
        assert SecurityContext.require() is p

    def test_task_isolation(self) -> None:
        """Each asyncio task gets its own context copy."""
        result_a: list[Principal | None] = []
        result_b: list[Principal | None] = []

        pa = Principal(subject="task-A")
        pb = Principal(subject="task-B")

        async def task_a() -> None:
            SecurityContext.set_current(pa)
            await asyncio.sleep(0)
            result_a.append(SecurityContext.get_current())

        async def task_b() -> None:
            SecurityContext.set_current(pb)
            await asyncio.sleep(0)
            result_b.append(SecurityContext.get_current())

        async def _run() -> None:
            await asyncio.gather(task_a(), task_b())

        asyncio.run(_run())
        assert result_a[0] is pa
        assert result_b[0] is pb

    def test_reset_token(self) -> None:
        p = Principal(subject="u")
        token = SecurityContext.set_current(p)
        assert token is not None  # token is returned for contextvar.reset


# ---------------------------------------------------------------------------
# Public surface smoke test
# ---------------------------------------------------------------------------


class TestPublicReExports:
    def test_all_symbols_importable(self) -> None:
        import importlib

        mod = importlib.import_module("mp_commons.kernel.security")
        for name in mod.__all__:
            assert hasattr(mod, name), f"{name!r} missing"
