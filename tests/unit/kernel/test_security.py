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


# ===========================================================================
# §62 — Authorization / RBAC
# ===========================================================================


class TestRBACRole:
    def test_exact_permission_match(self) -> None:
        from mp_commons.kernel.security import Permission, RBACRole

        role = RBACRole("editor", frozenset({Permission("articles:write")}))
        assert role.has_permission(Permission("articles:write"))

    def test_wildcard_resource_action(self) -> None:
        from mp_commons.kernel.security import Permission, RBACRole

        role = RBACRole("admin", frozenset({Permission("orders:*")}))
        assert role.has_permission("orders:read")
        assert role.has_permission("orders:write")
        assert role.has_permission("orders:delete")
        assert not role.has_permission("users:read")

    def test_global_wildcard(self) -> None:
        from mp_commons.kernel.security import Permission, RBACRole

        role = RBACRole("superadmin", frozenset({Permission("*")}))
        assert role.has_permission("anything:goes")
        assert role.has_permission("totally:random")

    def test_no_permission_match(self) -> None:
        from mp_commons.kernel.security import Permission, RBACRole

        role = RBACRole("viewer", frozenset({Permission("articles:read")}))
        assert not role.has_permission("articles:write")
        assert not role.has_permission("orders:read")

    def test_empty_permissions(self) -> None:
        from mp_commons.kernel.security import RBACRole

        role = RBACRole("guest")
        assert not role.has_permission("anything:read")

    def test_permission_by_string(self) -> None:
        from mp_commons.kernel.security import Permission, RBACRole

        role = RBACRole("dev", frozenset({Permission("repos:push")}))
        assert role.has_permission("repos:push")
        assert not role.has_permission("repos:admin")


class TestInMemoryRoleStore:
    def setup_method(self) -> None:
        from mp_commons.kernel.security import InMemoryRoleStore

        self.store = InMemoryRoleStore()

    def test_add_and_get_roles(self) -> None:
        from mp_commons.kernel.security import RBACRole

        role = RBACRole("editor")
        self.store.add_role("u1", role)
        assert role in self.store.get_roles("u1")

    def test_remove_role(self) -> None:
        from mp_commons.kernel.security import RBACRole

        role = RBACRole("editor")
        self.store.add_role("u1", role)
        self.store.remove_role("u1", role)
        assert role not in self.store.get_roles("u1")

    def test_get_roles_empty(self) -> None:
        assert self.store.get_roles("unknown") == []

    def test_has_permission_via_role(self) -> None:
        from mp_commons.kernel.security import Permission, RBACRole

        role = RBACRole("editor", frozenset({Permission("posts:write")}))
        self.store.add_role("u1", role)
        assert self.store.has_permission("u1", Permission("posts:write"))
        assert not self.store.has_permission("u1", Permission("posts:delete"))

    def test_clear_removes_all(self) -> None:
        from mp_commons.kernel.security import RBACRole

        self.store.add_role("u1", RBACRole("r"))
        self.store.clear()
        assert self.store.get_roles("u1") == []


class TestRBACPolicy:
    def test_direct_permission_allows(self) -> None:
        from mp_commons.kernel.security import Permission, Principal, RBACPolicy

        principal = Principal(
            subject="alice",
            permissions=frozenset({Permission("orders:cancel")}),
        )
        policy = RBACPolicy(Permission("orders:cancel"))
        assert policy.evaluate(principal).allowed

    def test_missing_permission_denies(self) -> None:
        from mp_commons.kernel.security import Permission, Principal, RBACPolicy

        principal = Principal(subject="bob")
        policy = RBACPolicy(Permission("orders:cancel"))
        result = policy.evaluate(principal)
        assert not result.allowed
        assert result.reason is not None
        assert "orders:cancel" in result.reason

    def test_wildcard_direct_permission_allows(self) -> None:
        from mp_commons.kernel.security import Permission, Principal, RBACPolicy

        principal = Principal(
            subject="admin",
            permissions=frozenset({Permission("orders:*")}),
        )
        policy = RBACPolicy("orders:cancel")
        assert policy.evaluate(principal).allowed

    def test_allows_via_role_store(self) -> None:
        from mp_commons.kernel.security import (
            InMemoryRoleStore,
            Permission,
            Principal,
            RBACPolicy,
            RBACRole,
        )

        store = InMemoryRoleStore()
        store.add_role("charlie", RBACRole("manager", frozenset({Permission("reports:export")})))
        principal = Principal(subject="charlie")

        policy = RBACPolicy("reports:export", role_store=store)
        assert policy.evaluate(principal).allowed

    def test_result_bool(self) -> None:
        from mp_commons.kernel.security import Permission, Principal, RBACPolicy

        p = Principal(subject="x", permissions=frozenset({Permission("a:b")}))
        result = RBACPolicy("a:b").evaluate(p)
        assert bool(result) is True


class TestRequirePermissionDecorator:
    def setup_method(self) -> None:
        from mp_commons.kernel.security import SecurityContext

        SecurityContext.clear()

    def test_async_allowed(self) -> None:
        import asyncio

        from mp_commons.kernel.security import Permission, Principal, SecurityContext, require_permission

        @require_permission("orders:read")
        async def handler() -> str:
            return "ok"

        principal = Principal(subject="u", permissions=frozenset({Permission("orders:read")}))
        SecurityContext.set_current(principal)
        result = asyncio.run(handler())
        assert result == "ok"

    def test_async_raises_forbidden(self) -> None:
        import asyncio

        from mp_commons.kernel.errors import ForbiddenError
        from mp_commons.kernel.security import Principal, SecurityContext, require_permission

        @require_permission("orders:cancel")
        async def handler() -> str:
            return "ok"

        principal = Principal(subject="u")
        SecurityContext.set_current(principal)
        with pytest.raises(ForbiddenError):
            asyncio.run(handler())

    def test_raises_unauthorized_when_no_principal(self) -> None:
        import asyncio

        from mp_commons.kernel.errors import UnauthorizedError
        from mp_commons.kernel.security import require_permission

        @require_permission("any:perm")
        async def handler() -> str:
            return "ok"

        with pytest.raises(UnauthorizedError):
            asyncio.run(handler())

    def test_sync_allowed(self) -> None:
        from mp_commons.kernel.security import Permission, Principal, SecurityContext, require_permission

        @require_permission("data:read")
        def sync_handler() -> str:
            return "synced"

        principal = Principal(subject="u", permissions=frozenset({Permission("data:read")}))
        SecurityContext.set_current(principal)
        assert sync_handler() == "synced"

    def test_sync_raises_forbidden(self) -> None:
        from mp_commons.kernel.errors import ForbiddenError
        from mp_commons.kernel.security import Principal, SecurityContext, require_permission

        @require_permission("data:delete")
        def sync_handler() -> str:
            return "deleted"

        SecurityContext.set_current(Principal(subject="u"))
        with pytest.raises(ForbiddenError):
            sync_handler()
