# Troubleshooting Guide

This guide covers the most common issues encountered when using `mp-commons`.

---

## 1. Async / Event Loop Issues

### "Event loop is already running" or "cannot run nested async"

**Symptom:** `RuntimeError: This event loop is already running` when calling
`asyncio.run()` inside an async context.

**Cause:** You are calling `asyncio.run()` from inside an already-running event
loop (common in Jupyter notebooks or certain test frameworks).

**Fix:**
```python
# Wrong — nests event loops
async def my_handler():
    result = asyncio.run(some_async_call())  # ❌

# Correct — await directly
async def my_handler():
    result = await some_async_call()  # ✅
```

In tests, if you see this with pytest-asyncio, ensure your test functions are
marked `@pytest.mark.asyncio` (or use `asyncio_mode = "auto"` in `pyproject.toml`).

---

### "Task got Future attached to a different loop"

**Symptom:** `ValueError: Task got Future <Future> attached to a different loop`.

**Cause:** An adapter was instantiated (and its internal client created) in one
event loop, then used in another loop. Common in tests that create fixtures at
module scope but run tests in new loops.

**Fix:** Use `scope="session"` or `scope="module"` fixtures consistently, or
instantiate the adapter inside the test function / the same loop where it is used.

```python
# pytest conftest.py
@pytest.fixture(scope="function")  # ✅ — new adapter per test
async def redis_cache():
    cache = RedisCache(url="redis://localhost:6379")
    async with cache:
        yield cache
```

---

### pytest-asyncio fixture scoping issues

If you see `ScopeMismatch: You tried to access the function-scope fixture X
from a session-scope fixture Y`, adjust scope consistency:

```toml
# pyproject.toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

Alternatively, decorate all async fixtures with the correct scope.

---

### ContextVar isolation in tests

`CorrelationContext`, `TenantContext`, and `SecurityContext` are backed by
`contextvars.ContextVar`.  asyncio tasks each get a **copy** of the context at
creation time; changes inside a task do not affect the parent unless explicitly
propagated.

In tests, always reset context between tests:

```python
@pytest.fixture(autouse=True)
def reset_contexts():
    CorrelationContext.reset()
    TenantContext.reset()
    yield
    CorrelationContext.reset()
    TenantContext.reset()
```

---

## 2. Adapter Import Errors

### `ImportError: ... is required for the X adapter`

All adapters in `mp-commons` use **lazy imports** — they only `import` the
optional third-party library when the adapter is actually used (not when the
module is imported).  This means:

```python
from mp_commons.adapters.elasticsearch import ElasticsearchClient
# ← No error yet, even if elasticsearch-py is not installed

client = ElasticsearchClient(url="...")
async with client:  # ← ImportError raised here if elasticsearch-py is missing
    ...
```

**Fix:** Install the required extra:

| Adapter | Extra |
|---|---|
| Elasticsearch | `pip install 'mp-commons[elasticsearch]'` |
| Redis | `pip install 'mp-commons[redis]'` |
| Kafka | `pip install 'mp-commons[kafka]'` |
| PostgreSQL / SQLAlchemy | `pip install 'mp-commons[sqlalchemy]'` |
| Azure adapters | `pip install 'mp-commons[azure]'` |
| GCP adapters | `pip install 'mp-commons[gcp]'` |
| Prometheus | `pip install 'mp-commons[prometheus]'` |
| gRPC | `pip install 'mp-commons[grpc]'` |

---

### `ModuleNotFoundError: No module named 'mp_commons.X'`

If you see this after installing `mp-commons`, ensure the package was installed
in editable mode in development:

```bash
uv pip install -e ".[dev]"
```

Also check that the import path matches the module layout:

```python
# Correct
from mp_commons.adapters.redis import RedisCache
from mp_commons.kernel.security import generate_code_verifier

# Incorrect (old path)
from mp_commons.redis import RedisCache  # ❌
```

---

## 3. mypy Strict Mode Issues

### `error: Cannot determine type of "X"` in adapters

Adapters use `Any` for optional imports to avoid hard mypy dependencies on
optional extras.  If you use adapters in mypy-strict typed code, add the
library's stub package:

```bash
pip install elasticsearch-stubs  # for mypy
```

Or suppress the error site-specifically:

```python
client: Any = ElasticsearchClient(...)  # type: ignore[var-annotated]
```

---

### `error: Incompatible return value type` from generics

`Result[T, E]`, `ElasticsearchRepository[T]`, and similar generics require
explicit type parameters when used as return types:

```python
async def find_order(order_id: str) -> Result[Order, str]:  # ✅
    ...

async def find_order(order_id: str) -> Result:  # ❌ — mypy will complain
    ...
```

---

### `error: Missing return statement` in async generators

Async generators that yield from `Protocol` implementations need `-> AsyncGenerator[T, None]`
return types, not `-> AsyncIterator[T]`, to satisfy mypy in strict mode.

---

## 4. Common Error Codes

| Error | Module | Cause |
|---|---|---|
| `ConcurrencyConflictError` | `resilience.circuit_breaker` / `event_sourcing` | Optimistic lock mismatch — retry the operation |
| `BackpressureError` | `resilience` | Too many in-flight commands; reduce concurrency or increase `max_concurrent` |
| `CircuitOpenError` | `resilience.circuit_breaker` | Downstream is unhealthy; wait for `timeout_seconds` then retry |
| `DeadlineExceededError` | `resilience.deadline` | Request exceeded its deadline; check slow dependencies |
| `IdempotencyConflictError` | `application.idempotency` | Duplicate request; return cached response |
| `TenantLeakError` | `testing` | Cross-tenant data leak detected in test; check repository `WHERE` clauses |
| `SchemaVersionError` | `observability.events` | Received event with future `schema_version`; upgrade the library |
| `JwtValidationError` | `kernel.security.jwt` | Invalid or expired JWT; check token expiry and signing key |

---

## 5. Performance Tuning Tips

### Connection pool exhaustion under high concurrency

If you see `asyncpg.exceptions.TooManyConnectionsError` or Redis `ConnectionError`,
increase the pool size:

```python
factory = SqlAlchemySessionFactory(
    url=DATABASE_URL,
    pool_size=20,      # default: 5
    max_overflow=40,   # allow burst connections
)
```

### Redis `asyncio.TimeoutError` under load

The default `socket_timeout` in `redis-py` is `None` (no timeout).  Set an
explicit timeout to surface slow Redis nodes:

```python
cache = RedisCache(url=REDIS_URL, socket_timeout=2.0)
```

### Kafka consumer lag

If Kafka consumers fall behind, increase `max_poll_records` and parallelize
per-partition processing with `aiokafka`'s `auto_commit_interval_ms`.
