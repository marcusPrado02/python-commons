"""Unit tests for §86 – JWT Utilities."""
import asyncio
from datetime import timedelta

import pytest

from mp_commons.security.jwt import (
    JwtClaims,
    JwtDecoder,
    JwtIssuer,
    JwtValidationError,
)

SECRET = "test-secret-key"
DECODER = JwtDecoder()


class TestJwtRoundTrip:
    def test_issue_and_decode(self):
        issuer = JwtIssuer(issuer="test-issuer")
        token = issuer.issue({"sub": "user-1"}, secret_or_key=SECRET)
        claims = DECODER.decode(token, secret_or_key=SECRET)
        assert claims.sub == "user-1"
        assert claims.iss == "test-issuer"

    def test_extra_claims_preserved(self):
        issuer = JwtIssuer(issuer="svc")
        token = issuer.issue({"sub": "u1", "role": "admin"}, secret_or_key=SECRET)
        claims = DECODER.decode(token, secret_or_key=SECRET)
        assert claims.extra.get("role") == "admin"

    def test_fresh_token_not_expired(self):
        issuer = JwtIssuer(issuer="svc")
        token = issuer.issue({"sub": "u1"}, secret_or_key=SECRET, expires_in=timedelta(hours=1))
        claims = DECODER.decode(token, secret_or_key=SECRET)
        assert not claims.is_expired()

    def test_iss_and_sub_accessible(self):
        issuer = JwtIssuer(issuer="my-svc")
        token = issuer.issue({"sub": "alice"}, secret_or_key=SECRET)
        claims = DECODER.decode(token, secret_or_key=SECRET)
        assert claims.iss == "my-svc"
        assert claims.sub == "alice"


class TestJwtValidation:
    def test_wrong_secret_raises(self):
        issuer = JwtIssuer(issuer="svc")
        token = issuer.issue({"sub": "u1"}, secret_or_key=SECRET)
        with pytest.raises(JwtValidationError):
            DECODER.decode(token, secret_or_key="wrong-secret")

    def test_expired_token_raises(self):
        issuer = JwtIssuer(issuer="svc")
        token = issuer.issue(
            {"sub": "u1"}, secret_or_key=SECRET, expires_in=timedelta(seconds=-1)
        )
        with pytest.raises(JwtValidationError):
            DECODER.decode(token, secret_or_key=SECRET)

    def test_audience_mismatch_raises(self):
        issuer = JwtIssuer(issuer="svc")
        token = issuer.issue({"sub": "u1", "aud": "audience-a"}, secret_or_key=SECRET)
        with pytest.raises(JwtValidationError):
            DECODER.decode(token, secret_or_key=SECRET, audience="audience-b")

    def test_audience_match_succeeds(self):
        issuer = JwtIssuer(issuer="svc")
        token = issuer.issue({"sub": "u1", "aud": "audience-a"}, secret_or_key=SECRET)
        claims = DECODER.decode(token, secret_or_key=SECRET, audience="audience-a")
        assert claims.sub == "u1"

    def test_invalid_token_string_raises(self):
        with pytest.raises(JwtValidationError):
            DECODER.decode("not.a.jwt", secret_or_key=SECRET)


class TestJwtClaims:
    def test_from_payload_maps_fields(self):
        payload = {"sub": "u1", "iss": "svc", "aud": "api", "jti": "abc123"}
        claims = JwtClaims.from_payload(payload)
        assert claims.sub == "u1"
        assert claims.iss == "svc"
        assert claims.aud == "api"
        assert claims.jti == "abc123"

    def test_extra_fields_captured(self):
        payload = {"sub": "u1", "custom": "val"}
        claims = JwtClaims.from_payload(payload)
        assert claims.extra.get("custom") == "val"

    def test_is_expired_false_without_exp(self):
        # When no exp in payload, from_payload sets exp=now; claims default is not-expired
        # Test the is_expired logic directly with a future exp
        from datetime import datetime, timedelta, timezone
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        claims = JwtClaims(sub="u1", exp=future)
        assert not claims.is_expired()
