"""Tests for §33.1‑33.4 – JWKSClient + OIDCTokenVerifier + KeycloakPolicyEngineAdapter."""
from __future__ import annotations

import asyncio
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

# ---------------------------------------------------------------------------
# Helpers – RSA key pair + JWT factories
# ---------------------------------------------------------------------------


def _make_rsa_key_pair():
    """Return (private_key, public_key) using `cryptography`."""
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.backends import default_backend

    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )
    return private_key, private_key.public_key()


def _make_token(
    private_key: Any,
    *,
    sub: str = "user-1",
    aud: str = "my-app",
    roles: list[str] | None = None,
    scope: str = "read write",
    tenant_id: str | None = "t1",
    exp_offset: int = 3600,
) -> str:
    import jwt

    claims: dict[str, Any] = {
        "sub": sub,
        "aud": aud,
        "iat": int(time.time()),
        "exp": int(time.time()) + exp_offset,
        "scope": scope,
    }
    if tenant_id is not None:
        claims["tenant_id"] = tenant_id
    if roles:
        claims["realm_access"] = {"roles": roles}

    return jwt.encode(claims, private_key, algorithm="RS256")


def _mock_jwks_client(public_key: Any) -> Any:
    """Return a JWKSClient mock whose get_signing_key returns `public_key`."""
    from mp_commons.adapters.keycloak.jwks import JWKSClient

    mock = MagicMock(spec=JWKSClient)
    signing_key = MagicMock()
    signing_key.key = public_key
    mock.get_signing_key = AsyncMock(return_value=signing_key)
    return mock


# ---------------------------------------------------------------------------
# JWKSClient unit tests
# ---------------------------------------------------------------------------


class TestJWKSClient:
    def test_instantiation(self) -> None:
        from mp_commons.adapters.keycloak.jwks import JWKSClient

        client = JWKSClient("https://example.com/certs")
        assert client._jwks_uri == "https://example.com/certs"
        assert client._client is None

    def test_invalidate_clears_internal_client(self) -> None:
        from mp_commons.adapters.keycloak.jwks import JWKSClient

        client = JWKSClient("https://example.com/certs")
        client._client = MagicMock()
        client.invalidate()
        assert client._client is None

    def test_keycloak_jwks_provider_alias(self) -> None:
        from mp_commons.adapters.keycloak.jwks import JWKSClient, KeycloakJwksProvider

        assert KeycloakJwksProvider is JWKSClient


# ---------------------------------------------------------------------------
# OIDCTokenVerifier
# ---------------------------------------------------------------------------


class TestOIDCTokenVerifier:
    def setup_method(self) -> None:
        self.private_key, self.public_key = _make_rsa_key_pair()

    def test_valid_token_returns_principal(self) -> None:
        from mp_commons.adapters.keycloak.verifier import OIDCTokenVerifier

        token = _make_token(
            self.private_key,
            sub="alice",
            aud="my-app",
            roles=["admin", "user"],
            scope="read write",
            tenant_id="tenant-A",
        )
        mock_jwks = _mock_jwks_client(self.public_key)
        verifier = OIDCTokenVerifier(mock_jwks, audience="my-app")

        principal = asyncio.run(verifier.verify(token))

        assert principal.subject == "alice"
        assert principal.tenant_id == "tenant-A"
        assert any(r.name == "admin" for r in principal.roles)
        assert any(r.name == "user" for r in principal.roles)
        assert any(p.value == "read" for p in principal.permissions)
        assert any(p.value == "write" for p in principal.permissions)

    def test_expired_token_raises_unauthorized(self) -> None:
        from mp_commons.adapters.keycloak.verifier import OIDCTokenVerifier
        from mp_commons.kernel.errors import UnauthorizedError

        token = _make_token(self.private_key, exp_offset=-1)
        mock_jwks = _mock_jwks_client(self.public_key)
        verifier = OIDCTokenVerifier(mock_jwks, audience="my-app")

        with pytest.raises(UnauthorizedError):
            asyncio.run(verifier.verify(token))

    def test_wrong_audience_raises_unauthorized(self) -> None:
        from mp_commons.adapters.keycloak.verifier import OIDCTokenVerifier
        from mp_commons.kernel.errors import UnauthorizedError

        token = _make_token(self.private_key, aud="other-app")
        mock_jwks = _mock_jwks_client(self.public_key)
        verifier = OIDCTokenVerifier(mock_jwks, audience="my-app")

        with pytest.raises(UnauthorizedError):
            asyncio.run(verifier.verify(token))

    def test_tampered_token_raises_unauthorized(self) -> None:
        from mp_commons.adapters.keycloak.verifier import OIDCTokenVerifier
        from mp_commons.kernel.errors import UnauthorizedError

        _, other_public = _make_rsa_key_pair()
        token = _make_token(self.private_key)
        mock_jwks = _mock_jwks_client(other_public)  # wrong key
        verifier = OIDCTokenVerifier(mock_jwks, audience="my-app")

        with pytest.raises(UnauthorizedError):
            asyncio.run(verifier.verify(token))

    def test_custom_realm_roles_claim(self) -> None:
        import jwt
        from mp_commons.adapters.keycloak.verifier import OIDCTokenVerifier

        claims = {
            "sub": "bob",
            "aud": "my-app",
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600,
            "my_roles": ["superuser"],
        }
        token = jwt.encode(claims, self.private_key, algorithm="RS256")
        mock_jwks = _mock_jwks_client(self.public_key)
        verifier = OIDCTokenVerifier(
            mock_jwks, audience="my-app", realm_roles_claim="my_roles"
        )

        principal = asyncio.run(verifier.verify(token))
        assert any(r.name == "superuser" for r in principal.roles)

    def test_no_roles_returns_empty_frozenset(self) -> None:
        from mp_commons.adapters.keycloak.verifier import OIDCTokenVerifier

        token = _make_token(self.private_key, roles=None)
        mock_jwks = _mock_jwks_client(self.public_key)
        verifier = OIDCTokenVerifier(mock_jwks, audience="my-app")

        principal = asyncio.run(verifier.verify(token))
        assert principal.roles == frozenset()


# ---------------------------------------------------------------------------
# KeycloakPolicyEngineAdapter (§33.3)
# ---------------------------------------------------------------------------


class TestKeycloakPolicyEngineAdapter:
    def _make_principal(self, roles: list[str], permissions: list[str]):
        from mp_commons.kernel.security.principal import Permission, Principal, Role

        return Principal(
            subject="user-1",
            tenant_id=None,
            roles=frozenset(Role(name=r) for r in roles),
            permissions=frozenset(Permission(value=p) for p in permissions),
            claims={},
        )

    def _make_context(self, principal, action: str, resource: str):
        from mp_commons.kernel.security.policy import PolicyContext

        return PolicyContext(principal=principal, action=action, resource=resource)

    def test_admin_role_allows_any_action(self) -> None:
        from mp_commons.adapters.keycloak.policy import KeycloakPolicyEngineAdapter
        from mp_commons.adapters.keycloak.verifier import OIDCTokenVerifier
        from mp_commons.kernel.security.policy import PolicyDecision

        mock_verifier = MagicMock(spec=OIDCTokenVerifier)
        adapter = KeycloakPolicyEngineAdapter(token_verifier=mock_verifier)
        principal = self._make_principal(roles=["admin"], permissions=[])
        ctx = self._make_context(principal, action="delete", resource="anything")

        decision = asyncio.run(adapter.evaluate(ctx))
        assert decision == PolicyDecision.ALLOW

    def test_required_permission_allows(self) -> None:
        from mp_commons.adapters.keycloak.policy import KeycloakPolicyEngineAdapter
        from mp_commons.adapters.keycloak.verifier import OIDCTokenVerifier
        from mp_commons.kernel.security.policy import PolicyDecision

        mock_verifier = MagicMock(spec=OIDCTokenVerifier)
        adapter = KeycloakPolicyEngineAdapter(token_verifier=mock_verifier)
        principal = self._make_principal(roles=[], permissions=["orders:create"])
        ctx = self._make_context(principal, action="create", resource="orders")

        decision = asyncio.run(adapter.evaluate(ctx))
        assert decision == PolicyDecision.ALLOW

    def test_missing_permission_denies(self) -> None:
        from mp_commons.adapters.keycloak.policy import KeycloakPolicyEngineAdapter
        from mp_commons.adapters.keycloak.verifier import OIDCTokenVerifier
        from mp_commons.kernel.security.policy import PolicyDecision

        mock_verifier = MagicMock(spec=OIDCTokenVerifier)
        adapter = KeycloakPolicyEngineAdapter(token_verifier=mock_verifier)
        principal = self._make_principal(roles=[], permissions=["orders:read"])
        ctx = self._make_context(principal, action="delete", resource="orders")

        decision = asyncio.run(adapter.evaluate(ctx))
        assert decision == PolicyDecision.DENY

    def test_no_role_no_permission_denies(self) -> None:
        from mp_commons.adapters.keycloak.policy import KeycloakPolicyEngineAdapter
        from mp_commons.adapters.keycloak.verifier import OIDCTokenVerifier
        from mp_commons.kernel.security.policy import PolicyDecision

        mock_verifier = MagicMock(spec=OIDCTokenVerifier)
        adapter = KeycloakPolicyEngineAdapter(token_verifier=mock_verifier)
        principal = self._make_principal(roles=[], permissions=[])
        ctx = self._make_context(principal, action="write", resource="item")

        decision = asyncio.run(adapter.evaluate(ctx))
        assert decision == PolicyDecision.DENY
