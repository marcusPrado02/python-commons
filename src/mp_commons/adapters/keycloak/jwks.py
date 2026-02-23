"""Keycloak adapter – JWKSClient backed by PyJWT (§33.1)."""
from __future__ import annotations

import asyncio
from typing import Any


def _require_pyjwt() -> Any:
    try:
        import jwt  # type: ignore[import-untyped]
        return jwt
    except ImportError as exc:
        raise ImportError(
            "Install 'mp-commons[keycloak]' (PyJWT[crypto]) to use this adapter"
        ) from exc


class JWKSClient:
    """Fetches and caches JWKS from Keycloak using :mod:`jwt.PyJWKClient`.

    The underlying ``PyJWKClient`` handles cache TTL internally; call
    :meth:`invalidate` to force a fresh fetch on the next request.

    Parameters
    ----------
    jwks_uri:
        Full URL of the JWKS endpoint, e.g.
        ``https://auth.example.com/realms/myrealm/protocol/openid-connect/certs``.
    cache_ttl:
        How many seconds to cache the JWKS locally.  Defaults to 300 s.
    """

    def __init__(self, jwks_uri: str, cache_ttl: float = 300.0) -> None:
        _require_pyjwt()  # validate dep at construction time
        self._jwks_uri = jwks_uri
        self._cache_ttl = cache_ttl
        self._client: Any = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_client(self) -> Any:
        if self._client is None:
            jwt = _require_pyjwt()
            self._client = jwt.PyJWKClient(
                self._jwks_uri,
                lifespan=int(self._cache_ttl),
            )
        return self._client

    # ------------------------------------------------------------------
    # Public async API
    # ------------------------------------------------------------------

    async def get_signing_key(self, token: str) -> Any:
        """Return the :class:`jwt.PyJWK` signing key for *token*.

        The call to ``PyJWKClient.get_signing_key_from_jwt`` is inherently
        synchronous (it may do an HTTP fetch on cache miss); we offload it to
        a thread to avoid blocking the event loop.
        """
        client = self._get_client()
        return await asyncio.to_thread(client.get_signing_key_from_jwt, token)

    def invalidate(self) -> None:
        """Force a fresh JWKS fetch on the next :meth:`get_signing_key` call."""
        self._client = None


# ---------------------------------------------------------------------------
# Backwards-compat alias (kept for existing code that references the old name)
# ---------------------------------------------------------------------------

KeycloakJwksProvider = JWKSClient

__all__ = ["JWKSClient", "KeycloakJwksProvider"]
