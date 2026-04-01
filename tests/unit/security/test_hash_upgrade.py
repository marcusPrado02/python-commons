"""Unit tests for ApiKeyHashUpgrade — bcrypt→argon2 migration (S-05)."""
from __future__ import annotations

import pytest
import bcrypt

from mp_commons.security.apikeys.generator import ApiKey, InMemoryApiKeyStore, _PREFIX_LEN
from mp_commons.security.apikeys.hash_upgrade import ApiKeyHashUpgrade, _is_bcrypt, _is_argon2


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_raw_key() -> str:
    import secrets
    import string
    chars = string.ascii_letters + string.digits
    prefix = "".join(secrets.choice(chars) for _ in range(_PREFIX_LEN))
    suffix = "".join(secrets.choice(chars) for _ in range(24))
    return prefix + suffix


def _bcrypt_record(raw_key: str, principal: str = "user-1") -> ApiKey:
    key_hash = bcrypt.hashpw(raw_key.encode(), bcrypt.gensalt(rounds=4))
    return ApiKey(
        key_id=raw_key[:_PREFIX_LEN],
        key_hash=key_hash,
        principal_id=principal,
        scopes=frozenset(["read"]),
    )


async def _argon2_record(raw_key: str) -> ApiKey:
    try:
        import argon2 as argon2_module
        hasher = argon2_module.PasswordHasher(time_cost=1, memory_cost=8192, parallelism=1)
        h = hasher.hash(raw_key)
        return ApiKey(
            key_id=raw_key[:_PREFIX_LEN],
            key_hash=h.encode() if isinstance(h, str) else h,
            principal_id="user-2",
        )
    except ImportError:
        pytest.skip("argon2-cffi not installed")


# ---------------------------------------------------------------------------
# Hash detection helpers
# ---------------------------------------------------------------------------


class TestHashDetection:
    def test_is_bcrypt_with_bcrypt_hash(self):
        h = bcrypt.hashpw(b"x" * 10, bcrypt.gensalt(rounds=4))
        assert _is_bcrypt(h)

    def test_is_bcrypt_false_for_argon2(self):
        assert not _is_bcrypt(b"$argon2id$v=19$m=65536,t=2,p=1$abc$def")

    def test_is_argon2_with_argon2_hash(self):
        assert _is_argon2(b"$argon2id$v=19$m=65536,t=2,p=1$abc$def")

    def test_is_argon2_false_for_bcrypt(self):
        h = bcrypt.hashpw(b"x" * 10, bcrypt.gensalt(rounds=4))
        assert not _is_argon2(h)


# ---------------------------------------------------------------------------
# verify_and_upgrade — bcrypt path
# ---------------------------------------------------------------------------


class TestBcryptUpgrade:
    @pytest.mark.asyncio
    async def test_returns_none_for_key_too_short(self):
        store = InMemoryApiKeyStore()
        upgrader = ApiKeyHashUpgrade(store=store)
        result = await upgrader.verify_and_upgrade("short")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_for_missing_record(self):
        store = InMemoryApiKeyStore()
        upgrader = ApiKeyHashUpgrade(store=store)
        raw = _make_raw_key()
        result = await upgrader.verify_and_upgrade(raw)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_for_wrong_password(self):
        store = InMemoryApiKeyStore()
        raw = _make_raw_key()
        record = _bcrypt_record(raw)
        await store.save(record)
        upgrader = ApiKeyHashUpgrade(store=store)

        other = _make_raw_key()[:_PREFIX_LEN] + raw[_PREFIX_LEN:]
        # Replace prefix so key_id matches but password is wrong
        bad_key = raw[:_PREFIX_LEN] + "WRONGWRONG0000000000000"
        result = await upgrader.verify_and_upgrade(bad_key)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_for_revoked_key(self):
        store = InMemoryApiKeyStore()
        raw = _make_raw_key()
        record = _bcrypt_record(raw)
        await store.save(record)
        await store.revoke(record.key_id)

        upgrader = ApiKeyHashUpgrade(store=store)
        result = await upgrader.verify_and_upgrade(raw)
        assert result is None

    @pytest.mark.asyncio
    async def test_upgrades_bcrypt_to_argon2_on_success(self):
        try:
            import argon2  # noqa: F401
        except ImportError:
            pytest.skip("argon2-cffi not installed")

        store = InMemoryApiKeyStore()
        raw = _make_raw_key()
        record = _bcrypt_record(raw)
        await store.save(record)

        upgrader = ApiKeyHashUpgrade(
            store=store, argon2_time_cost=1, argon2_memory_cost=8192, argon2_parallelism=1
        )
        result = await upgrader.verify_and_upgrade(raw)

        assert result is not None
        assert result.key_id == record.key_id
        # The stored hash should now be argon2
        updated = await store.find_by_id(record.key_id)
        assert updated is not None
        assert _is_argon2(updated.key_hash)

    @pytest.mark.asyncio
    async def test_preserves_metadata_after_upgrade(self):
        try:
            import argon2  # noqa: F401
        except ImportError:
            pytest.skip("argon2-cffi not installed")

        store = InMemoryApiKeyStore()
        raw = _make_raw_key()
        record = _bcrypt_record(raw)
        await store.save(record)

        upgrader = ApiKeyHashUpgrade(
            store=store, argon2_time_cost=1, argon2_memory_cost=8192, argon2_parallelism=1
        )
        result = await upgrader.verify_and_upgrade(raw)

        assert result is not None
        assert result.principal_id == record.principal_id
        assert result.scopes == record.scopes
        assert result.expires_at == record.expires_at
        assert result.revoked == record.revoked


# ---------------------------------------------------------------------------
# verify_and_upgrade — argon2 path
# ---------------------------------------------------------------------------


class TestArgon2Verify:
    @pytest.mark.asyncio
    async def test_verifies_existing_argon2_hash(self):
        try:
            import argon2  # noqa: F401
        except ImportError:
            pytest.skip("argon2-cffi not installed")

        store = InMemoryApiKeyStore()
        raw = _make_raw_key()
        record = await _argon2_record(raw)
        await store.save(record)

        upgrader = ApiKeyHashUpgrade(
            store=store, argon2_time_cost=1, argon2_memory_cost=8192, argon2_parallelism=1
        )
        result = await upgrader.verify_and_upgrade(raw)
        assert result is not None
        assert result.key_id == record.key_id

    @pytest.mark.asyncio
    async def test_argon2_wrong_password_returns_none(self):
        try:
            import argon2  # noqa: F401
        except ImportError:
            pytest.skip("argon2-cffi not installed")

        store = InMemoryApiKeyStore()
        raw = _make_raw_key()
        record = await _argon2_record(raw)
        await store.save(record)

        upgrader = ApiKeyHashUpgrade(
            store=store, argon2_time_cost=1, argon2_memory_cost=8192, argon2_parallelism=1
        )
        bad_key = raw[:_PREFIX_LEN] + "WRONGWRONGWRONGWRONG0000"
        result = await upgrader.verify_and_upgrade(bad_key)
        assert result is None


# ---------------------------------------------------------------------------
# Graceful degradation — upgrade failure
# ---------------------------------------------------------------------------


class TestGracefulDegradation:
    @pytest.mark.asyncio
    async def test_returns_record_when_argon2_not_installed(self, monkeypatch):
        """When argon2-cffi is missing, the original bcrypt record is returned."""
        store = InMemoryApiKeyStore()
        raw = _make_raw_key()
        record = _bcrypt_record(raw)
        await store.save(record)

        import mp_commons.security.apikeys.hash_upgrade as mod

        def raise_import(*args, **kwargs):
            raise ImportError("no argon2")

        monkeypatch.setattr(mod, "_require_argon2", raise_import)

        upgrader = ApiKeyHashUpgrade(store=store)
        upgrader._argon2_hasher = None  # reset cached hasher
        result = await upgrader.verify_and_upgrade(raw)
        # Should still return the valid record (graceful fallback)
        assert result is not None
        assert result.key_id == record.key_id
        # Hash should remain bcrypt
        stored = await store.find_by_id(record.key_id)
        assert _is_bcrypt(stored.key_hash)
