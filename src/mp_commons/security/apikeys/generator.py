from __future__ import annotations

import hashlib
import os
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Protocol

import bcrypt

__all__ = [
    "ApiKey",
    "ApiKeyGenerator",
    "ApiKeyStore",
    "ApiKeyVerifier",
    "InMemoryApiKeyStore",
]

_PREFIX_LEN = 8


@dataclass
class ApiKey:
    """Stored API key record — never stores the raw key."""

    key_id: str            # public prefix shown to user for identification
    key_hash: bytes        # bcrypt hash of full key
    principal_id: str
    scopes: frozenset[str] = field(default_factory=frozenset)
    expires_at: datetime | None = None
    revoked: bool = False

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) >= self.expires_at

    def is_valid(self) -> bool:
        return not self.revoked and not self.is_expired()


class ApiKeyStore(Protocol):
    async def save(self, key: ApiKey) -> None: ...
    async def find_by_id(self, key_id: str) -> ApiKey | None: ...
    async def revoke(self, key_id: str) -> None: ...


class InMemoryApiKeyStore:
    def __init__(self) -> None:
        self._store: dict[str, ApiKey] = {}

    async def save(self, key: ApiKey) -> None:
        self._store[key.key_id] = key

    async def find_by_id(self, key_id: str) -> ApiKey | None:
        return self._store.get(key_id)

    async def revoke(self, key_id: str) -> None:
        if key_id in self._store:
            self._store[key_id].revoked = True


class ApiKeyGenerator:
    """Generates API keys; raw key shown once, hash stored."""

    def __init__(self, rounds: int = 4) -> None:
        # Low rounds for tests; production should use >=12
        self._rounds = rounds

    def generate(
        self,
        principal_id: str,
        scopes: frozenset[str] | set[str] | list[str] = frozenset(),
        ttl_days: int | None = None,
    ) -> tuple[str, ApiKey]:
        raw_key = secrets.token_urlsafe(32)
        key_id = raw_key[:_PREFIX_LEN]
        key_hash = bcrypt.hashpw(raw_key.encode(), bcrypt.gensalt(rounds=self._rounds))
        expires_at = (
            datetime.now(timezone.utc) + timedelta(days=ttl_days)
            if ttl_days is not None
            else None
        )
        record = ApiKey(
            key_id=key_id,
            key_hash=key_hash,
            principal_id=principal_id,
            scopes=frozenset(scopes),
            expires_at=expires_at,
        )
        return raw_key, record


class ApiKeyVerifier:
    """Verifies a raw API key against stored `ApiKey` records."""

    def __init__(self, store: ApiKeyStore) -> None:
        self._store = store

    async def verify(self, raw_key: str) -> ApiKey | None:
        if len(raw_key) < _PREFIX_LEN:
            return None
        key_id = raw_key[:_PREFIX_LEN]
        record = await self._store.find_by_id(key_id)
        if record is None or not record.is_valid():
            return None
        if bcrypt.checkpw(raw_key.encode(), record.key_hash):
            return record
        return None
