"""Unit tests for in-memory test fakes."""

from __future__ import annotations

import pytest

from mp_commons.kernel.messaging import (
    IdempotencyKey,
    Message,
    MessageHeaders,
    OutboxRecord,
)
from mp_commons.kernel.types import CorrelationId
from mp_commons.testing.fakes import (
    FakeClock,
    FakePolicyEngine,
    InMemoryIdempotencyStore,
    InMemoryMessageBus,
    InMemoryOutboxRepository,
)
from mp_commons.kernel.security import PolicyDecision


# ---------------------------------------------------------------------------
# FakeClock
# ---------------------------------------------------------------------------


class TestFakeClock:
    def test_returns_frozen_clock(self) -> None:
        clock = FakeClock()
        t1 = clock.now()
        t2 = clock.now()
        assert t1 == t2  # frozen

    def test_advance_moves_time(self) -> None:
        clock = FakeClock()
        t0 = clock.now()
        clock.advance(hours=1)
        assert clock.now() > t0


# ---------------------------------------------------------------------------
# InMemoryMessageBus
# ---------------------------------------------------------------------------


class TestInMemoryMessageBus:
    @pytest.mark.asyncio
    async def test_publish_records_message(self) -> None:
        bus = InMemoryMessageBus()
        msg = Message(
            topic="orders",
            payload={"id": "1"},
            headers=MessageHeaders(correlation_id=CorrelationId("cid-1")),
        )
        await bus.publish(msg)
        assert len(bus.published) == 1
        assert bus.published[0] is msg

    @pytest.mark.asyncio
    async def test_of_topic_filters(self) -> None:
        bus = InMemoryMessageBus()
        for topic in ("orders", "shipments", "orders"):
            await bus.publish(Message(topic=topic, payload={}))
        assert len(bus.of_topic("orders")) == 2
        assert len(bus.of_topic("shipments")) == 1

    @pytest.mark.asyncio
    async def test_clear_empties_bus(self) -> None:
        bus = InMemoryMessageBus()
        await bus.publish(Message(topic="t", payload={}))
        bus.clear()
        assert bus.published == []


# ---------------------------------------------------------------------------
# InMemoryOutboxRepository
# ---------------------------------------------------------------------------


class TestInMemoryOutboxRepository:
    @pytest.mark.asyncio
    async def test_save_and_list_pending(self) -> None:
        repo = InMemoryOutboxRepository()
        rec = OutboxRecord(topic="orders", payload=b'{"id":1}')
        await repo.save(rec)
        pending = await repo.list_pending(limit=10)
        assert len(pending) == 1
        assert pending[0].topic == "orders"

    @pytest.mark.asyncio
    async def test_mark_dispatched_removes_from_pending(self) -> None:
        repo = InMemoryOutboxRepository()
        rec = OutboxRecord(topic="t", payload=b"{}")
        await repo.save(rec)
        await repo.mark_dispatched(rec.id)
        pending = await repo.list_pending(limit=10)
        assert pending == []


# ---------------------------------------------------------------------------
# InMemoryIdempotencyStore
# ---------------------------------------------------------------------------


class TestInMemoryIdempotencyStore:
    @pytest.mark.asyncio
    async def test_not_found_before_set(self) -> None:
        store = InMemoryIdempotencyStore()
        key = IdempotencyKey("op-1", "resource-1")
        result = await store.get(key)
        assert result is None

    @pytest.mark.asyncio
    async def test_set_and_get(self) -> None:
        store = InMemoryIdempotencyStore()
        key = IdempotencyKey("op-1", "resource-1")
        await store.set(key, b"result-payload")
        result = await store.get(key)
        assert result is not None
        assert result.response_payload == b"result-payload"

    @pytest.mark.asyncio
    async def test_exists_returns_true_after_set(self) -> None:
        store = InMemoryIdempotencyStore()
        key = IdempotencyKey("op-2", "resource-2")
        assert not await store.exists(key)
        await store.set(key, b"x")
        assert await store.exists(key)


# ---------------------------------------------------------------------------
# FakePolicyEngine
# ---------------------------------------------------------------------------


class TestFakePolicyEngine:
    def test_allow_by_default(self) -> None:
        engine = FakePolicyEngine(default=PolicyDecision.ALLOW)
        from mp_commons.kernel.security import Principal, PolicyContext
        p = Principal(subject="user-1")
        ctx = PolicyContext(principal=p, resource="orders", action="read")
        assert engine.evaluate(ctx) == PolicyDecision.ALLOW

    def test_deny_specific_resource_action(self) -> None:
        engine = FakePolicyEngine(default=PolicyDecision.ALLOW)
        engine.deny("orders", "delete")

        from mp_commons.kernel.security import Principal, PolicyContext
        p = Principal(subject="user-1")
        allow_ctx = PolicyContext(principal=p, resource="orders", action="read")
        deny_ctx = PolicyContext(principal=p, resource="orders", action="delete")
        assert engine.evaluate(allow_ctx) == PolicyDecision.ALLOW
        assert engine.evaluate(deny_ctx) == PolicyDecision.DENY
