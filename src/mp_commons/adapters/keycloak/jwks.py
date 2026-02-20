"""Keycloak adapter – KeycloakJwksProvider."""
from __future__ import annotations

from typing import Any


def _require_jose() -> Any:
    try:
        from jose import jwt  # type: ignore[import-untyped]
        return jwt
    except ImportError as exc:
        raise ImportError("Install 'mp-commons[keycloak]' (python-jose[cryptography]) to use this adapter") from exc


class KeycloakJwksProvider:
    """Fetches and caches JWKS from Keycloak."""

    def __init__(self, jwks_uri: str) -> None:
        try:
            import httpx  # noqa: F401
        except ImportError as exc:
            raise ImportError("Install 'httpx' to use KeycloakJwksProvider") from exc
        self._jwks_uri = jwks_uri
        self._keys: dict[str, Any] | None = None

    async def get_keys(self) -> dict[str, Any]:
        if self._keys is not None:
            return self._keys
        import httpx  # type: ignore[import-untyped]
        async with httpx.AsyncClient() as client:
            resp = await client.get(self._jwks_uri)
            resp.raise_for_status()
            self._keys = resp.json()
            return self._keys

    def invalidate(self) -> None:
        self._keys = None


__all__ = ["KeycloakJwksProvider"]
