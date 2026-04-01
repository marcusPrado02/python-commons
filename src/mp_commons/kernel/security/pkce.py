"""PKCE (Proof Key for Code Exchange) helpers — RFC 7636 (S-03).

Provides primitives for generating and verifying PKCE challenges in an
OAuth 2.0 / OIDC authorization code flow.

Usage (client — generating the pair)::

    from mp_commons.kernel.security.pkce import generate_pkce_pair

    code_verifier, code_challenge = generate_pkce_pair()
    # Pass code_challenge + method="S256" in the /authorize request.
    # Later, include code_verifier in the /token request.

Usage (server — verifying the pair)::

    from mp_commons.kernel.security.pkce import verify_code_challenge

    # Raises PKCEVerificationError on mismatch
    verify_code_challenge(stored_challenge, received_verifier, method="S256")
"""
from __future__ import annotations

import base64
import hashlib
import os
import re

# RFC 7636 §4.1 — verifier length 43-128 chars, unreserved chars only
_VERIFIER_RE = re.compile(r"^[A-Za-z0-9\-._~]{43,128}$")
_DEFAULT_VERIFIER_BYTES = 32  # generates 43 chars after base64url (no padding)


class PKCEError(ValueError):
    """Raised for invalid PKCE parameters or verification failure."""


class PKCEVerificationError(PKCEError):
    """Raised when the code_verifier does not match the stored code_challenge."""


def generate_code_verifier(length_bytes: int = _DEFAULT_VERIFIER_BYTES) -> str:
    """Generate a cryptographically random PKCE code verifier.

    Parameters
    ----------
    length_bytes:
        Number of raw random bytes.  The returned base64url-encoded string will
        be ``ceil(4 * length_bytes / 3)`` characters long (always ≥43 and ≤128
        for the default range 32–96 bytes).

    Returns
    -------
    str
        URL-safe base64 string without ``=`` padding.
    """
    if not (32 <= length_bytes <= 96):
        raise PKCEError(f"length_bytes must be 32–96, got {length_bytes}")
    raw = os.urandom(length_bytes)
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def compute_code_challenge(code_verifier: str, method: str = "S256") -> str:
    """Derive a code challenge from a code verifier.

    Parameters
    ----------
    code_verifier:
        The PKCE code verifier string (43–128 URL-safe chars).
    method:
        Challenge method — ``"S256"`` (SHA-256, recommended) or ``"plain"``.

    Returns
    -------
    str
        The code challenge to include in the ``/authorize`` request.

    Raises
    ------
    PKCEError
        If *code_verifier* does not conform to RFC 7636 or *method* is unknown.
    """
    if not _VERIFIER_RE.match(code_verifier):
        raise PKCEError(
            "code_verifier must be 43–128 URL-safe characters "
            f"([A-Za-z0-9-._~]), got {len(code_verifier)} chars"
        )
    if method == "S256":
        digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
        return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    if method == "plain":
        return code_verifier
    raise PKCEError(f"Unsupported PKCE method: {method!r}. Use 'S256' or 'plain'.")


def verify_code_challenge(
    stored_challenge: str,
    received_verifier: str,
    method: str = "S256",
) -> None:
    """Verify that *received_verifier* matches *stored_challenge*.

    This is the server-side check performed when exchanging the authorization
    code for a token.

    Parameters
    ----------
    stored_challenge:
        The ``code_challenge`` value submitted during the ``/authorize`` step.
    received_verifier:
        The ``code_verifier`` submitted in the token exchange request.
    method:
        The ``code_challenge_method`` stored alongside the challenge.

    Raises
    ------
    PKCEVerificationError
        If the verifier does not derive to the stored challenge.
    PKCEError
        If *received_verifier* is malformed or *method* is unknown.
    """
    expected = compute_code_challenge(received_verifier, method=method)
    # Use compare_digest to avoid timing attacks
    import hmac
    if not hmac.compare_digest(expected.encode("ascii"), stored_challenge.encode("ascii")):
        raise PKCEVerificationError(
            "code_verifier does not match the stored code_challenge"
        )


def generate_pkce_pair(method: str = "S256") -> tuple[str, str]:
    """Generate a (code_verifier, code_challenge) pair in one call.

    Returns
    -------
    tuple[str, str]
        ``(code_verifier, code_challenge)`` — the verifier is secret (client
        keeps it) while the challenge is sent to the authorization server.
    """
    verifier = generate_code_verifier()
    challenge = compute_code_challenge(verifier, method=method)
    return verifier, challenge


__all__ = [
    "PKCEError",
    "PKCEVerificationError",
    "compute_code_challenge",
    "generate_code_verifier",
    "generate_pkce_pair",
    "verify_code_challenge",
]
