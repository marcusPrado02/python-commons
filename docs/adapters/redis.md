# Redis Adapter Runbook

## Installation

```bash
pip install 'mp-commons[redis]'
```

## Required Environment Variables

| Variable | Example | Description |
|---|---|---|
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL |

## Basic Usage

```python
from mp_commons.adapters.redis import RedisCache

cache = RedisCache(url="redis://localhost:6379/0")
async with cache:
    await cache.set("key", {"data": 1}, ttl=60)
    value = await cache.get("key")
```

## Health Check

```python
from mp_commons.adapters.redis import RedisCache
from mp_commons.observability.health import HealthCheck

async def redis_health() -> bool:
    cache = RedisCache(url=REDIS_URL)
    async with cache:
        return await cache.ping()
```

Register with `HealthRegistry`:
```python
registry.register(HealthCheck(name="redis", check=redis_health))
```

## Rate Limiter

```python
from mp_commons.adapters.redis.rate_limiter import RedisRateLimiter
from mp_commons.application.rate_limit import Quota

quota = Quota(key="api", limit=100, window_seconds=60)
limiter = RedisRateLimiter(cache=cache)
allowed = await limiter.check(quota, identifier="user:123")
```

## Common Error Codes

| Error | Cause | Fix |
|---|---|---|
| `redis.exceptions.ConnectionError` | Redis not reachable | Check `REDIS_URL` and firewall rules |
| `redis.exceptions.AuthenticationError` | Wrong password | Add `?password=...` to URL or use `redis://:password@host` |
| `asyncio.TimeoutError` | Slow Redis node | Set `socket_timeout=2.0` in `RedisCache(url=..., socket_timeout=2.0)` |
| `redis.exceptions.ResponseError: OOM` | Redis out of memory | Set `maxmemory` and eviction policy in Redis config |

## Performance Tuning

- **Connection pool size**: Default is 10. Increase for high-concurrency services:
  ```python
  RedisCache(url=REDIS_URL, max_connections=50)
  ```
- **Socket timeout**: Always set an explicit timeout to surface slow nodes:
  ```python
  RedisCache(url=REDIS_URL, socket_timeout=2.0, socket_connect_timeout=1.0)
  ```
- **Pipelining**: Use `cache.pipeline()` for bulk operations to reduce round-trips.
- **Key expiry**: Always set TTL on cache entries to avoid unbounded memory growth.
