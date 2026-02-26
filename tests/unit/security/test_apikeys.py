"""Unit tests for §85 – API Keys."""
import asyncio
from datetime import datetime, timezone

import pytest

from mp_commons.security.apikeys import (
    ApiKey,
    ApiKeyGenerator,
    ApiKeyVerifier,
    InMemoryApiKeyStore,
)


def make_store_and_gen():
    store = InMemoryApiKeyStore()
    gen = ApiKeyGenerator(rounds=4)
    return store, gen


class TestApiKeyGenerator:
    def test_returns_raw_key_and_model(self):
        _, gen = make_store_and_gen()
        raw, api_key = gen.generate("user-1")
        assert isinstance(raw, str)
        assert isinstance(api_key, ApiKey)

    def test_key_id_is_prefix_of_raw(self):
        _, gen = make_store_and_gen()
        raw, api_key = gen.generate("user-1")
        assert raw.startswith(api_key.key_id)

    def test_different_keys_each_call(self):
        _, gen = make_store_and_gen()
        raw1, _ = gen.generate("user-1")
        raw2, _ = gen.generate("user-1")
        assert raw1 != raw2

    def test_key_not_expired_by_default(self):
        _, gen = make_store_and_gen()
        raw, api_key = gen.generate("user-1")
        assert not api_key.is_expired()

    def test_key_with_ttl(self):
        _, gen = make_store_and_gen()
        raw, api_key = gen.generate("user-1", ttl_days=30)
        assert api_key.expires_at is not None
        assert not api_key.is_expired()

    def test_scopes_stored(self):
        _, gen = make_store_and_gen()
        raw, api_key = gen.generate("user-1", scopes=["read", "write"])
        assert "read" in api_key.scopes
        assert "write" in api_key.scopes

    def test_hash_differs_from_raw(self):
        _, gen = make_store_and_gen()
        raw, api_key = gen.generate("user-1")
        assert raw.encode() != api_key.key_hash


class TestApiKeyVerifier:
    def test_verify_correct_key(self):
        store, gen = make_store_and_gen()
        raw, api_key = gen.generate("user-1")
        asyncio.run(store.save(api_key))
        verifier = ApiKeyVerifier(store)
        result = asyncio.run(verifier.verify(raw))
        assert result is not None
        assert result.key_id == api_key.key_id

    def test_verify_wrong_key_returns_none(self):
        store, gen = make_store_and_gen()
        raw, api_key = gen.generate("user-1")
        asyncio.run(store.save(api_key))
        verifier = ApiKeyVerifier(store)
        result = asyncio.run(verifier.verify(raw + "WRONG"))
        assert result is None

    def test_verify_nonexistent_key_id_returns_none(self):
        store, gen = make_store_and_gen()
        verifier = ApiKeyVerifier(store)
        result = asyncio.run(verifier.verify("XYZXYZXZ_not_there"))
        assert result is None

    def test_verify_revoked_key_returns_none(self):
        store, gen = make_store_and_gen()
        raw, api_key = gen.generate("user-1")
        asyncio.run(store.save(api_key))
        asyncio.run(store.revoke(api_key.key_id))
        verifier = ApiKeyVerifier(store)
        result = asyncio.run(verifier.verify(raw))
        assert result is None

    def test_verify_expired_key_returns_none(self):
        store, gen = make_store_and_gen()
        raw, api_key = gen.generate("user-1", ttl_days=-1)  # expired yesterday
        asyncio.run(store.save(api_key))
        verifier = ApiKeyVerifier(store)
        result = asyncio.run(verifier.verify(raw))
        assert result is None


class TestApiKeyModel:
    def test_is_valid_true_when_fresh(self):
        _, gen = make_store_and_gen()
        _, api_key = gen.generate("user-1")
        assert api_key.is_valid()

    def test_is_valid_false_when_revoked(self):
        _, gen = make_store_and_gen()
        _, api_key = gen.generate("user-1")
        revoked = api_key.__class__(
            key_id=api_key.key_id,
            key_hash=api_key.key_hash,
            principal_id=api_key.principal_id,
            scopes=api_key.scopes,
            expires_at=api_key.expires_at,
            revoked=True,
        )
        assert not revoked.is_valid()

    def test_is_expired_false_when_no_expiry(self):
        _, gen = make_store_and_gen()
        _, api_key = gen.generate("user-1")
        assert not api_key.is_expired()
