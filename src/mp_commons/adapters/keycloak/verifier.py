"""Keycloak adapter – OIDCTokenVerifier using PyJWT (§33.2)."""
from __future__ import annotations

from typing import Any

from mp_commons.kernel.errors import UnauthorizedError
from mp_commons.kernel.security import Permission, Principal, Role
from mp_commons.adapters.keycloak.jwks import JWKSClient, _require_pyjwt


class OIDCTokenVerifier:
    """Verify a Bearer JWT and extract a :class:`Principal`.

    Parameters
    ----------
    jwks_client:
        A :class:`JWKSClient` (or any compatible object with an async
        ``get_signing_key(token: str)`` method).
    audience:
        Expected ``aud`` claim value.  The token is rejected if the audience
        does not match.
    algorithms:
        Allowed signature algorithms.  Defaults to ``["RS256"]``.
    realm_roles_claim:
        Dot-separated path to the list of realm roles inside the JWT claims.
        Defaults to ``"realm_access.roles"``.
    permissions_claim:
        Claim name whose space-separated value lists granted OAuth scopes /
        permissions.  Defaults to ``"scope"``.
    """

    def __init__(
        self,
        jwks_client: JWKSClient,
        audience: str,
        algorithms: list[str] | None = None,
        realm_roles_claim: str = "realm_access.roles",
        permissions_claim: str = "scope",
    ) -> None:
        self._jwks = jwks_client
        self._audience = audience
        self._algorithms = algorithms or ["RS256"]
        self._realm_roles_claim = realm_roles_claim
        self._permissions_claim = permissions_claim

    async def verify(self, token: str) -> Principal:
        """Verify *token* and return the extracted :class:`Principal`.

        Raises :class:`~mp_commons.kernel.errors.UnauthorizedError` on any
        verification failure (expired, wrong audience, invalid signature, …).
        """
        jwt = _require_pyjwt()
        try:
            signing_key = await self._jwks.get_signing_key(token)
            claims: dict[str, Any] = jwt.decode(
                token,
                signing_key.key,
                algorithms=self._algorithms,
                audience=self._audience,
            )
        except jwt.InvalidTokenError as exc:
            raise UnauthorizedError(f"Invalid token: {exc}") from exc
        except Exception as exc:  # network errors, etc.
            raise UnauthorizedError(f"Token verification failed: {exc}") from exc

        roles = self._extract_roles(claims)
        permissions = self._extract_permissions(claims)

        return Principal(
            subject=claims.get("sub", ""),
            tenant_id=claims.get("tenant_id"),
            roles=frozenset(Role(r) for r in roles),
            permissions=frozenset(Permission(p) for p in permissions),
            claims=dict(claims),
        )

    def _extract_roles(self, claims: dict[str, Any]) -> list[str]:
        parts = self._realm_roles_claim.split(".")
        node: Any = claims
        for part in parts:
            if not isinstance(node, dict):
                return []
            node = node.get(part)
        if isinstance(node, list):
            return [r for r in node if isinstance(r, str)]
        return []

    def _extract_permissions(self, claims: dict[str, Any]) -> list[str]:
        scope: str = claims.get(self._permissions_claim, "") or ""
        return [s for s in scope.split() if s]


__all__ = ["OIDCTokenVerifier"]
