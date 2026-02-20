"""Redis adapter – RedisLock."""
from __future__ import annotations

from mp_commons.adapters.redis.cache import RedisCache


class RedisLock:
    """Simple async distributed lock using Redis SET NX PX."""

    def __init__(self, cache: RedisCache, name: str, ttl_ms: int = 5000) -> None:
        self._cache = cache
        self._name = f"lock:{name}"
        self._ttl_ms = ttl_ms
        self._token: str | None = None

    async def acquire(self) -> bool:
        import uuid
        token = str(uuid.uuid4())
        client = self._cache._client  # noqa: SLF001
        result = await client.set(self._name, token, nx=True, px=self._ttl_ms)
        if result:
            self._token = token
            return True
        return False

    async def release(self) -> None:
        if self._token is None:
            return
        script = """
        if redis.call("GET", KEYS[1]) == ARGV[1] then
            return redis.call("DEL", KEYS[1])
        else
            return 0
        end
        """
        client = self._cache._client  # noqa: SLF001
        await client.eval(script, 1, self._name, self._token)
        self._token = None

    async def __aenter__(self) -> "RedisLock":
        acquired = await self.acquire()
        if not acquired:
            from mp_commons.kernel.errors import ConflictError
            raise ConflictError(f"Could not acquire lock '{self._name}'")
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.release()


__all__ = ["RedisLock"]
