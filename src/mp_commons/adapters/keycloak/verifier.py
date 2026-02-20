"""Keycloak adapter – OIDCTokenVerifier."""
from __future__ import annotations

from typing import Any

from mp_commons.kernel.errors import UnauthorizedError
from mp_commons.kernel.security import Permission, Principal, Role
from mp_commons.adapters.keycloak.jwks import KeycloakJwksProvider, _require_jose


class OIDCTokenVerifier:
    """Verify a Bearer JWT and return a ``Principal``."""

    def __init__(
        self,
        jwks_provider: KeycloakJwksProvider,
        audience: str,
        algorithms: list[str] | None = None,
        realm_roles_claim: str = "realm_access.roles",
        permissions_claim: str = "scope",
    ) -> None:
        self._jwks = jwks_provider
        self._audience = audience
        self._algorithms = algorithms or ["RS256"]
        self._realm_roles_claim = realm_roles_claim
        self._permissions_claim = permissions_claim

    async def verify(self, token: str) -> Principal:
        jwt = _require_jose()
        try:
            keys = await self._jwks.get_keys()
            claims = jwt.decode(token, keys, algorithms=self._algorithms, audience=self._audience)
        except Exception as exc:
            raise UnauthorizedError(f"Invalid token: {exc}") from exc

        roles = self._extract_roles(claims)
        permissions = self._extract_permissions(claims)

        return Principal(
            subject=claims.get("sub", ""),
            tenant_id=claims.get("tenant_id"),
            roles=frozenset(Role(r) for r in roles),
            permissions=frozenset(Permission(p) for p in permissions),
            claims=claims,
        )

    def _extract_roles(self, claims: dict[str, Any]) -> list[str]:
        parts = self._realm_roles_claim.split(".")
        node: Any = claims
        for p in parts:
            if not isinstance(node, dict):
                return []
            node = node.get(p)
        if isinstance(node, list):
            return [r for r in node if isinstance(r, str)]
        return []

    def _extract_permissions(self, claims: dict[str, Any]) -> list[str]:
        scope: str = claims.get("scope", "") or ""
        return [s for s in scope.split() if s]


__all__ = ["OIDCTokenVerifier"]
