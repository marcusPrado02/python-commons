# Migration Guide — 0.x → 1.0

This guide covers all breaking changes introduced between the `0.x` series and
the `1.0.0` release and provides step-by-step instructions for upgrading.

---

## Quick Summary

| Area | What Changed |
|---|---|
| `InboxRecord` | Two parallel types now exist — kernel (bytes) vs application (Any) |
| `OutboxRecord.payload` | Changed from `dict` to `bytes` |
| `InboxProcessor` | Now requires `InboxStore`, not `InboxRepository` |
| `KafkaOutboxDispatcher` | Constructor kwargs renamed: `producer` → `bus`, `outbox_repo` → `repo` |
| `CircuitBreakerPolicy` | Kwarg `recovery_timeout` → `timeout_seconds` |
| `RedisRateLimiter` | Constructor takes `cache: RedisCache`; method `acquire()` → `check()` |
| `Quota` | Field `requests` → `limit` |
| `TenantContext.set()` | Requires `TenantId`, not `str` |
| `FastAPIHealthRouter` | `registry_factory` kwarg removed; use `readiness_checks` |
| Structured Events | `StructuredEvent` now has `schema_version` field |

---

## Detailed Breaking Changes

### 1. `OutboxRecord.payload` is now `bytes`

**Before (0.x):**
```python
OutboxRecord(
    payload={"order_id": "123"},  # dict ❌
)
```

**After (1.0):**
```python
import json

OutboxRecord(
    payload=json.dumps({"order_id": "123"}).encode(),  # bytes ✅
)
```

**Why:** Ensures the outbox is transport-agnostic and avoids silent serialization
mismatches when switching between JSON, MessagePack, or Avro.

---

### 2. Two `InboxRecord` types — kernel vs application

There are now two distinct `InboxRecord` dataclasses:

| Module | Purpose | Key Fields |
|---|---|---|
| `mp_commons.kernel.messaging` | Transport-layer record (Kafka/NATS raw) | `message_id`, `topic`, `payload: bytes` |
| `mp_commons.application.inbox` | Application-layer record (processor) | `source`, `event_type`, `payload: Any` |

If you were using `InboxRecord` from `mp_commons.kernel.messaging` with
`InboxProcessor`, switch to the application-layer type:

```python
# Before
from mp_commons.kernel.messaging import InboxRecord  # ❌ wrong type for processor

# After
from mp_commons.application.inbox import InboxRecord  # ✅
record = InboxRecord(source="orders", event_type="OrderCreated", payload=payload_dict)
```

---

### 3. `InboxProcessor` requires `InboxStore`, not `InboxRepository`

**Before (0.x):**
```python
from mp_commons.testing.fakes.inbox import InMemoryInboxRepository

processor = InboxProcessor(store=InMemoryInboxRepository(), command_bus=bus)  # ❌
```

**After (1.0):**
```python
from mp_commons.application.inbox import InMemoryInboxStore

processor = InboxProcessor(store=InMemoryInboxStore(), command_bus=bus)  # ✅
```

`InboxStore` is a lighter `Protocol` with `save`, `load`, and `is_duplicate` methods.
`InboxRepository` (kernel) still exists for transport-layer persistence.

---

### 4. `KafkaOutboxDispatcher` constructor kwargs renamed

**Before (0.x):**
```python
KafkaOutboxDispatcher(producer=producer, outbox_repo=repo)  # ❌
```

**After (1.0):**
```python
KafkaOutboxDispatcher(bus=producer, repo=repo)  # ✅
```

---

### 5. `CircuitBreakerPolicy` kwarg renamed

**Before (0.x):**
```python
CircuitBreakerPolicy(failure_threshold=5, recovery_timeout=30)  # ❌
```

**After (1.0):**
```python
CircuitBreakerPolicy(failure_threshold=5, timeout_seconds=30.0)  # ✅
```

---

### 6. `RedisRateLimiter` API change

**Before (0.x):**
```python
limiter = RedisRateLimiter(redis_url="redis://localhost:6379")
await limiter.acquire(key="user:1", limit=100, window=60)  # ❌
```

**After (1.0):**
```python
from mp_commons.application.rate_limit import Quota
from mp_commons.adapters.redis import RedisCache
from mp_commons.adapters.redis.rate_limiter import RedisRateLimiter

cache = RedisCache(url="redis://localhost:6379")
limiter = RedisRateLimiter(cache=cache)  # ✅
quota = Quota(key="api", limit=100, window_seconds=60)
allowed = await limiter.check(quota, "user:1")  # ✅
```

---

### 7. `Quota` field renamed

**Before (0.x):**
```python
Quota(key="api", requests=100, window_seconds=60)  # ❌
```

**After (1.0):**
```python
Quota(key="api", limit=100, window_seconds=60)  # ✅
```

---

### 8. `TenantContext.set()` requires `TenantId`

**Before (0.x):**
```python
TenantContext.set("tenant-abc")  # str ❌
```

**After (1.0):**
```python
from mp_commons.kernel.types.ids import TenantId

TenantContext.set(TenantId("tenant-abc"))  # ✅
```

---

### 9. `FastAPIHealthRouter` — `registry_factory` removed

**Before (0.x):**
```python
FastAPIHealthRouter(registry_factory=lambda: registry)  # ❌
```

**After (1.0):**
```python
FastAPIHealthRouter(readiness_checks=[my_check_fn])  # ✅
```

---

### 10. `StructuredEvent.schema_version` added

Events now include a `schema_version: int` field (default: `1`). Events with
a `schema_version` higher than the library's `CURRENT_SCHEMA_VERSION` raise
`SchemaVersionError` at deserialization time.

If you persist structured events, ensure you add `schema_version: 1` to
existing records before upgrading, or the `from_dict()` path will default
gracefully (missing field is treated as version 1).

---

## Step-by-Step Upgrade Checklist

1. **Update the package**: `uv pip install 'mp-commons>=1.0.0'`
2. **Search for `OutboxRecord` usages** where `payload=` is a `dict` — JSON-encode to bytes.
3. **Search for `InboxRecord` imports** — decide kernel vs application based on usage.
4. **Replace `InMemoryInboxRepository` with `InMemoryInboxStore`** in test fixtures.
5. **Replace `KafkaOutboxDispatcher(producer=..., outbox_repo=...)` with `(bus=..., repo=...)`**.
6. **Replace `recovery_timeout=` with `timeout_seconds=`** in CircuitBreaker config.
7. **Replace `Quota(requests=...)` with `Quota(limit=...)`**.
8. **Replace `TenantContext.set(str)` with `TenantContext.set(TenantId(str))`**.
9. **Run your test suite** — `uv run pytest tests/unit -x -q`.
10. **Run integration tests** — `uv run pytest tests/integration -m integration`.

---

## Removed APIs

The following APIs were removed in 1.0 and have no direct replacements:

| Removed | Reason |
|---|---|
| `mp_commons.redis.RedisCache` | Use `mp_commons.adapters.redis.RedisCache` |
| `InboxRepository` as `InboxProcessor` dependency | Replaced by lighter `InboxStore` protocol |
| `CircuitBreakerPolicy.recovery_timeout` | Renamed to `timeout_seconds` for clarity |

---

## Getting Help

- File an issue at `github.com/marcusPrado02/python-commons/issues`
- See `docs/guides/troubleshooting.md` for common errors and fixes
