"""Redis adapter – RedisCache."""
from __future__ import annotations

from typing import Any


def _require_redis() -> Any:
    try:
        import redis.asyncio as aioredis
        return aioredis
    except ImportError as exc:
        raise ImportError("Install 'mp-commons[redis]' to use the Redis adapter") from exc


class RedisCache:
    """Simple async Redis cache wrapper."""

    def __init__(self, url: str, **kwargs: Any) -> None:
        aioredis = _require_redis()
        self._client = aioredis.from_url(url, **kwargs)

    async def get(self, key: str) -> bytes | None:
        return await self._client.get(key)

    async def set(self, key: str, value: bytes, ttl: int | None = None) -> None:
        await self._client.set(key, value, ex=ttl)

    async def delete(self, key: str) -> None:
        await self._client.delete(key)

    async def exists(self, key: str) -> bool:
        return bool(await self._client.exists(key))

    async def close(self) -> None:
        await self._client.aclose()


__all__ = ["RedisCache"]
