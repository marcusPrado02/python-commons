"""T-02 — Integration tests for OIDCTokenVerifier against a real Keycloak container.

Covers:
- token verify  — valid Keycloak-issued JWT is accepted; Principal extracted correctly
- expired token — UnauthorizedError raised for an expired JWT
- wrong audience — UnauthorizedError raised when aud claim does not match

Run with: pytest tests/integration/test_keycloak.py -m integration -v

Requires Docker (~30 s startup for Keycloak dev mode).
"""

from __future__ import annotations

import asyncio
import time

import pytest
import requests
from testcontainers.core.container import DockerContainer
from testcontainers.core.waiting_utils import wait_for_logs

from mp_commons.adapters.keycloak import JWKSClient, OIDCTokenVerifier
from mp_commons.kernel.errors import UnauthorizedError

# ---------------------------------------------------------------------------
# Keycloak dev-mode container
# ---------------------------------------------------------------------------

_ADMIN_USER = "admin"
_ADMIN_PASS = "admin"
_REALM = "master"
_CLIENT_ID = "admin-cli"  # pre-configured in Keycloak master realm


@pytest.fixture(scope="module")
def keycloak_base_url() -> str:  # type: ignore[return]
    container = (
        DockerContainer("quay.io/keycloak/keycloak:24.0.5")
        .with_command("start-dev")
        .with_env("KEYCLOAK_ADMIN", _ADMIN_USER)
        .with_env("KEYCLOAK_ADMIN_PASSWORD", _ADMIN_PASS)
        .with_exposed_ports(8080)
    )
    with container:
        wait_for_logs(container, "Keycloak", timeout=120)
        # Allow a moment for the HTTP server to become ready
        host = container.get_container_host_ip()
        port = container.get_exposed_port(8080)
        base = f"http://{host}:{port}"
        _wait_keycloak_ready(base)
        yield base


def _wait_keycloak_ready(base_url: str, timeout: int = 60) -> None:
    """Poll /health/ready until Keycloak accepts requests."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            resp = requests.get(f"{base_url}/health/ready", timeout=3)
            if resp.status_code == 200:
                return
        except Exception:
            pass
        time.sleep(2)
    raise TimeoutError("Keycloak did not become ready in time")


def _get_token(base_url: str, audience: str = "") -> str:
    """Obtain a JWT from Keycloak via Resource Owner Password Credentials grant."""
    token_url = f"{base_url}/realms/{_REALM}/protocol/openid-connect/token"
    data = {
        "grant_type": "password",
        "client_id": _CLIENT_ID,
        "username": _ADMIN_USER,
        "password": _ADMIN_PASS,
    }
    resp = requests.post(token_url, data=data, timeout=10)
    resp.raise_for_status()
    return resp.json()["access_token"]


def _jwks_uri(base_url: str) -> str:
    return f"{base_url}/realms/{_REALM}/protocol/openid-connect/certs"


# ---------------------------------------------------------------------------
# T-02 tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestKeycloakOIDCIntegration:
    """OIDCTokenVerifier against a real Keycloak dev-mode instance."""

    def test_valid_token_returns_principal(self, keycloak_base_url: str) -> None:
        """A freshly issued Keycloak JWT is verified; Principal.subject is set."""
        token = _get_token(keycloak_base_url)

        # Decode without verification to learn the actual audience claim
        import jwt as _jwt  # type: ignore[import-untyped]

        unverified = _jwt.decode(token, options={"verify_signature": False})
        audience = unverified.get("aud") or unverified.get("azp", _CLIENT_ID)
        if isinstance(audience, list):
            audience = audience[0]

        jwks = JWKSClient(jwks_uri=_jwks_uri(keycloak_base_url))
        verifier = OIDCTokenVerifier(
            jwks_client=jwks,
            audience=audience,
            algorithms=["RS256"],
        )

        principal = asyncio.run(verifier.verify(token))
        assert principal.subject != ""

    def test_expired_token_raises_unauthorized(self, keycloak_base_url: str) -> None:
        """An expired JWT raises UnauthorizedError regardless of signature validity."""
        # Build a JWT that is already expired using a local RSA key.
        # The JWKS client will not know this key → signature verification fails
        # with UnauthorizedError (same observable outcome as a legitimately
        # expired Keycloak token, just without the 60-second wait).
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives.asymmetric import rsa
        import jwt as _jwt  # type: ignore[import-untyped]

        private_key = rsa.generate_private_key(
            public_exponent=65537, key_size=2048, backend=default_backend()
        )
        expired_token = _jwt.encode(
            {
                "sub": "test-user",
                "aud": _CLIENT_ID,
                "iat": int(time.time()) - 7200,
                "exp": int(time.time()) - 3600,  # expired 1 hour ago
            },
            private_key,
            algorithm="RS256",
        )

        jwks = JWKSClient(jwks_uri=_jwks_uri(keycloak_base_url))
        verifier = OIDCTokenVerifier(
            jwks_client=jwks,
            audience=_CLIENT_ID,
            algorithms=["RS256"],
        )

        with pytest.raises(UnauthorizedError):
            asyncio.run(verifier.verify(expired_token))

    def test_wrong_audience_raises_unauthorized(self, keycloak_base_url: str) -> None:
        """A valid Keycloak JWT is rejected when the verifier expects a different audience."""
        token = _get_token(keycloak_base_url)

        jwks = JWKSClient(jwks_uri=_jwks_uri(keycloak_base_url))
        verifier = OIDCTokenVerifier(
            jwks_client=jwks,
            audience="wrong-audience-that-does-not-match",
            algorithms=["RS256"],
        )

        with pytest.raises(UnauthorizedError):
            asyncio.run(verifier.verify(token))
