"""Redis adapter – RedisIdempotencyStore."""
from __future__ import annotations

import json

from mp_commons.kernel.messaging import IdempotencyKey, IdempotencyRecord, IdempotencyStore
from mp_commons.adapters.redis.cache import RedisCache


class RedisIdempotencyStore(IdempotencyStore):
    """Redis-backed idempotency store (TTL-based expiration)."""

    def __init__(self, cache: RedisCache, default_ttl: int = 86400) -> None:
        self._cache = cache
        self._ttl = default_ttl

    def _key(self, key: IdempotencyKey) -> str:
        return f"idempotency:{key}"

    async def get(self, key: IdempotencyKey) -> IdempotencyRecord | None:
        raw = await self._cache.get(self._key(key))
        if raw is None:
            return None
        data = json.loads(raw)
        return IdempotencyRecord(**data)

    async def save(self, key: IdempotencyKey, record: IdempotencyRecord) -> None:
        data = json.dumps({"key": record.key, "response": None, "status": record.status}).encode()
        await self._cache.set(self._key(key), data, ttl=self._ttl)

    async def complete(self, key: IdempotencyKey, response: bytes) -> None:
        record = await self.get(key)
        if record is None:
            return
        data = json.dumps({"key": record.key, "response": response.decode(), "status": "COMPLETED"}).encode()
        await self._cache.set(self._key(key), data, ttl=self._ttl)


__all__ = ["RedisIdempotencyStore"]
