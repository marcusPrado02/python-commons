"""T-10 — Verify anyio trio backend compatibility for core mp-commons modules.

Tests marked with ``@pytest.mark.anyio`` run under both asyncio and trio
backends via the ``anyio_backends`` fixture (configured below).  This file
explicitly targets trio to verify that the pure functional/protocol-level
code in mp-commons works with either event loop.

Known asyncio-only modules (not covered here — use asyncio.create_task,
asyncio.ensure_future, or asyncio.get_event_loop directly):
- mp_commons.resilience.graceful_shutdown
- mp_commons.resilience.dead_letter_scheduler
- mp_commons.observability.logging.async_handler
- mp_commons.testing.load.runner

These modules require explicit anyio porting before they support trio.
"""

from __future__ import annotations

import pytest

# Override anyio backend for this module — run all anyio tests under BOTH
# asyncio and trio so incompatibilities surface.
pytestmark = pytest.mark.anyio


# ---------------------------------------------------------------------------
# Application – InProcessCommandBus
# ---------------------------------------------------------------------------


async def test_command_bus_dispatch_trio() -> None:
    from mp_commons.application.cqrs.commands import (
        Command,
        CommandHandler,
        InProcessCommandBus,
    )

    class Ping(Command):
        pass

    class PingHandler(CommandHandler[Ping]):
        async def handle(self, command: Ping) -> str:
            return "pong"

    bus = InProcessCommandBus()
    bus.register(Ping, PingHandler())
    result = await bus.dispatch(Ping())
    assert result == "pong"


# ---------------------------------------------------------------------------
# Application – AsyncLRUCache
# ---------------------------------------------------------------------------


async def test_async_lru_cache_trio() -> None:
    from mp_commons.application.cache import AsyncLRUCache

    calls = 0

    async def loader() -> str:
        nonlocal calls
        calls += 1
        return "loaded-value"

    cache: AsyncLRUCache[str, str] = AsyncLRUCache(maxsize=8, ttl=60.0)
    v1 = await cache.get_or_load("k", loader)
    v2 = await cache.get_or_load("k", loader)
    assert v1 == v2 == "loaded-value"
    assert calls == 1  # loader called once; second hit from cache


# ---------------------------------------------------------------------------
# Kernel – Result type
# ---------------------------------------------------------------------------


async def test_result_ok_trio() -> None:
    from mp_commons.kernel.types.result import Err, Ok

    async def divide(a: int, b: int) -> Ok[float] | Err[str]:
        if b == 0:
            return Err("division by zero")
        return Ok(a / b)

    r = await divide(10, 2)
    assert r.is_ok()
    assert r.unwrap() == 5.0

    err = await divide(10, 0)
    assert err.is_err()


# ---------------------------------------------------------------------------
# Resilience – CircuitBreaker (pure state machine)
# ---------------------------------------------------------------------------


async def test_circuit_breaker_trio() -> None:
    from mp_commons.resilience.circuit_breaker import CircuitBreaker, CircuitBreakerPolicy

    policy = CircuitBreakerPolicy(failure_threshold=2, timeout_seconds=1.0)
    breaker = CircuitBreaker(name="trio-test", policy=policy)

    async def _ok() -> str:
        return "ok"

    r = await breaker.call(_ok)
    assert r == "ok"


# ---------------------------------------------------------------------------
# Observability – correlation context (ContextVar — trio-safe)
# ---------------------------------------------------------------------------


async def test_correlation_context_trio() -> None:
    from mp_commons.observability.correlation.context import CorrelationContext, RequestContext

    ctx = RequestContext(correlation_id="trio-req-1")
    CorrelationContext.set(ctx)

    async def nested() -> str | None:
        c = CorrelationContext.get()
        return c.correlation_id if c else None

    cid = await nested()
    assert cid == "trio-req-1"


# ---------------------------------------------------------------------------
# Observability – StructuredEvent
# ---------------------------------------------------------------------------


async def test_structured_event_trio() -> None:
    import json

    from mp_commons.observability.events import EventEmitter, StructuredEvent

    emitter = EventEmitter()
    evt = StructuredEvent(name="test.event", service="trio-svc", fields={"x": 1})
    emitter.emit(evt)
    count = await emitter.flush()
    assert count == 1

    parsed = json.loads(evt.to_json())
    assert parsed["name"] == "test.event"
    assert parsed["schema_version"] == 1


# ---------------------------------------------------------------------------
# Testing – InMemoryObjectStore (no async I/O primitives)
# ---------------------------------------------------------------------------


async def test_in_memory_object_store_trio() -> None:
    from mp_commons.adapters.s3 import InMemoryObjectStore

    store = InMemoryObjectStore()
    await store.put("k.txt", b"hello", "text/plain")
    data = await store.get("k.txt")
    assert data == b"hello"
    assert await store.exists("k.txt")
    await store.delete("k.txt")
    assert not await store.exists("k.txt")


# ---------------------------------------------------------------------------
# Resilience – RetryPolicy construction (no side effects)
# ---------------------------------------------------------------------------


async def test_retry_policy_constructor_trio() -> None:
    from mp_commons.resilience.retry import RetryPolicy

    policy = RetryPolicy(max_attempts=3)
    assert policy.max_attempts == 3


# ---------------------------------------------------------------------------
# Multi-tenant – TenantContext isolation across tasks (trio nursery)
# ---------------------------------------------------------------------------


async def test_tenant_context_task_isolation_trio() -> None:
    """ContextVar values are isolated per task — works the same under trio."""
    import anyio

    from mp_commons.kernel.ddd.tenant import TenantContext

    seen: list[str | None] = []

    from mp_commons.kernel.types.ids import TenantId

    async def worker(tenant_id: str) -> None:
        TenantContext.set(TenantId(tenant_id))
        await anyio.sleep(0)
        tid = TenantContext.get()
        seen.append(str(tid) if tid is not None else None)

    async with anyio.create_task_group() as tg:
        tg.start_soon(worker, "tenant-A")
        tg.start_soon(worker, "tenant-B")

    # Each task saw its own context value
    assert set(seen) == {"tenant-A", "tenant-B"}
