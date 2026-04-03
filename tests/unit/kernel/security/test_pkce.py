"""Unit tests for PKCE helpers — RFC 7636 (S-03)."""

from __future__ import annotations

import base64
import hashlib

import pytest

from mp_commons.kernel.security.pkce import (
    PKCEError,
    PKCEVerificationError,
    compute_code_challenge,
    generate_code_verifier,
    generate_pkce_pair,
    verify_code_challenge,
)

# ---------------------------------------------------------------------------
# generate_code_verifier
# ---------------------------------------------------------------------------


class TestGenerateCodeVerifier:
    def test_returns_string(self):
        v = generate_code_verifier()
        assert isinstance(v, str)

    def test_length_within_rfc_bounds(self):
        v = generate_code_verifier()
        # Default: 32 bytes → 43 chars (base64url without padding)
        assert 43 <= len(v) <= 128

    def test_only_unreserved_chars(self):
        import re

        v = generate_code_verifier()
        assert re.fullmatch(r"[A-Za-z0-9\-._~]+", v)

    def test_randomness(self):
        v1 = generate_code_verifier()
        v2 = generate_code_verifier()
        assert v1 != v2

    def test_custom_length_bytes(self):
        v = generate_code_verifier(length_bytes=64)
        # 64 bytes → ceil(4*64/3)=86 base64url chars
        assert len(v) == 86

    def test_min_length(self):
        v = generate_code_verifier(length_bytes=32)
        assert len(v) >= 43

    def test_max_length(self):
        v = generate_code_verifier(length_bytes=96)
        assert len(v) <= 128

    def test_invalid_low_length(self):
        with pytest.raises(PKCEError):
            generate_code_verifier(length_bytes=16)

    def test_invalid_high_length(self):
        with pytest.raises(PKCEError):
            generate_code_verifier(length_bytes=128)

    def test_no_padding(self):
        v = generate_code_verifier()
        assert "=" not in v


# ---------------------------------------------------------------------------
# compute_code_challenge
# ---------------------------------------------------------------------------


class TestComputeCodeChallenge:
    def _known_challenge(self, verifier: str) -> str:
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")

    def test_s256_matches_spec(self):
        verifier = generate_code_verifier()
        challenge = compute_code_challenge(verifier, method="S256")
        assert challenge == self._known_challenge(verifier)

    def test_s256_default_method(self):
        verifier = generate_code_verifier()
        assert compute_code_challenge(verifier) == compute_code_challenge(verifier, method="S256")

    def test_plain_method(self):
        verifier = generate_code_verifier()
        challenge = compute_code_challenge(verifier, method="plain")
        assert challenge == verifier

    def test_unknown_method_raises(self):
        verifier = generate_code_verifier()
        with pytest.raises(PKCEError, match="Unsupported"):
            compute_code_challenge(verifier, method="MD5")

    def test_short_verifier_raises(self):
        with pytest.raises(PKCEError):
            compute_code_challenge("short")

    def test_verifier_with_invalid_chars_raises(self):
        # 43 chars but contains space (invalid)
        bad = "a" * 42 + " "
        with pytest.raises(PKCEError):
            compute_code_challenge(bad)

    def test_challenge_no_padding(self):
        verifier = generate_code_verifier()
        challenge = compute_code_challenge(verifier, method="S256")
        assert "=" not in challenge

    def test_deterministic(self):
        verifier = generate_code_verifier()
        c1 = compute_code_challenge(verifier)
        c2 = compute_code_challenge(verifier)
        assert c1 == c2


# ---------------------------------------------------------------------------
# verify_code_challenge
# ---------------------------------------------------------------------------


class TestVerifyCodeChallenge:
    def test_valid_pair_does_not_raise(self):
        verifier = generate_code_verifier()
        challenge = compute_code_challenge(verifier)
        verify_code_challenge(challenge, verifier)  # must not raise

    def test_wrong_verifier_raises(self):
        verifier = generate_code_verifier()
        challenge = compute_code_challenge(verifier)
        other = generate_code_verifier()
        with pytest.raises(PKCEVerificationError):
            verify_code_challenge(challenge, other)

    def test_plain_method_valid(self):
        verifier = generate_code_verifier()
        challenge = compute_code_challenge(verifier, method="plain")
        verify_code_challenge(challenge, verifier, method="plain")  # must not raise

    def test_plain_method_wrong_raises(self):
        verifier = generate_code_verifier()
        challenge = compute_code_challenge(verifier, method="plain")
        other = generate_code_verifier()
        with pytest.raises(PKCEVerificationError):
            verify_code_challenge(challenge, other, method="plain")

    def test_invalid_verifier_raises_pkce_error(self):
        with pytest.raises(PKCEError):
            verify_code_challenge("any-challenge", "bad")

    def test_pkce_verification_error_is_pkce_error(self):
        assert issubclass(PKCEVerificationError, PKCEError)


# ---------------------------------------------------------------------------
# generate_pkce_pair
# ---------------------------------------------------------------------------


class TestGeneratePkcePair:
    def test_returns_two_strings(self):
        verifier, challenge = generate_pkce_pair()
        assert isinstance(verifier, str)
        assert isinstance(challenge, str)

    def test_challenge_derives_from_verifier(self):
        verifier, challenge = generate_pkce_pair()
        assert challenge == compute_code_challenge(verifier)

    def test_pair_verifies(self):
        verifier, challenge = generate_pkce_pair()
        verify_code_challenge(challenge, verifier)  # must not raise

    def test_plain_pair(self):
        verifier, challenge = generate_pkce_pair(method="plain")
        assert verifier == challenge
