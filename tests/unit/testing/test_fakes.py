"""Unit tests for in-memory test fakes (§36)."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

from mp_commons.kernel.messaging import (
    IdempotencyKey,
    IdempotencyRecord,
    InboxRecord,
    InboxStatus,
    Message,
    MessageHeaders,
    OutboxRecord,
    OutboxStatus,
)
from mp_commons.kernel.security import PolicyContext, PolicyDecision, Principal
from mp_commons.kernel.time import FrozenClock
from mp_commons.testing.fakes import (
    FakeClock,
    FakePolicyEngine,
    InMemoryIdempotencyStore,
    InMemoryInboxRepository,
    InMemoryMessageBus,
    InMemoryOutboxRepository,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _headers() -> MessageHeaders:
    return MessageHeaders(extra={})


def _dt() -> datetime:
    return datetime.now(UTC)


def _message(topic: str = "orders") -> Message:
    return Message(
        id=str(uuid.uuid4()),
        topic=topic,
        payload={"x": 1},
        headers=_headers(),
        occurred_at=_dt(),
    )


def _outbox_record(topic: str = "orders") -> OutboxRecord:
    return OutboxRecord(
        id=str(uuid.uuid4()),
        topic=topic,
        payload=b'{"id":1}',
        headers=_headers(),
        created_at=_dt(),
    )


def _inbox_record(message_id: str | None = None) -> InboxRecord:
    return InboxRecord(
        id=str(uuid.uuid4()),
        message_id=message_id or str(uuid.uuid4()),
        topic="events",
        payload=b"{}",
        headers=_headers(),
        received_at=_dt(),
    )


def _idempotency_key(op: str = "op-1") -> IdempotencyKey:
    return IdempotencyKey(client_key="client-1", operation=op)


def _idempotency_record(key: IdempotencyKey) -> IdempotencyRecord:
    return IdempotencyRecord(key=key, created_at=_dt())


def _principal() -> Principal:
    return Principal(subject="user-1", claims={})


def _ctx(resource: str = "orders", action: str = "read") -> PolicyContext:
    return PolicyContext(
        principal=_principal(),
        resource=resource,
        action=action,
        attributes={},
    )


# ---------------------------------------------------------------------------
# §36.1  FakeClock
# ---------------------------------------------------------------------------


class TestFakeClock:
    def test_returns_frozen_clock(self) -> None:
        clock = FakeClock()
        assert isinstance(clock, FrozenClock)

    def test_is_frozen(self) -> None:
        clock = FakeClock()
        t1 = clock.now()
        t2 = clock.now()
        assert t1 == t2

    def test_pinned_to_2026_01_01(self) -> None:
        clock = FakeClock()
        assert clock.now().year == 2026
        assert clock.now().month == 1
        assert clock.now().day == 1

    def test_advance_hours(self) -> None:
        clock = FakeClock()
        t0 = clock.now()
        clock.advance(hours=1)
        assert clock.now() > t0
        delta = clock.now() - t0
        assert int(delta.total_seconds()) == 3600

    def test_advance_minutes(self) -> None:
        clock = FakeClock()
        t0 = clock.now()
        clock.advance(minutes=30)
        assert int((clock.now() - t0).total_seconds()) == 1800

    def test_advance_days(self) -> None:
        clock = FakeClock()
        t0 = clock.now()
        clock.advance(days=1)
        assert (clock.now() - t0).days == 1

    def test_multiple_advances_accumulate(self) -> None:
        clock = FakeClock()
        t0 = clock.now()
        clock.advance(hours=1)
        clock.advance(hours=1)
        assert int((clock.now() - t0).total_seconds()) == 7200


# ---------------------------------------------------------------------------
# §36.2  InMemoryMessageBus
# ---------------------------------------------------------------------------


class TestInMemoryMessageBus:
    def test_publish_records_message(self) -> None:
        bus = InMemoryMessageBus()
        msg = _message("orders")
        asyncio.run(bus.publish(msg))
        assert len(bus.published) == 1
        assert bus.published[0] is msg

    def test_publish_batch(self) -> None:
        bus = InMemoryMessageBus()
        msgs = [_message("t") for _ in range(3)]
        asyncio.run(bus.publish_batch(msgs))
        assert len(bus.published) == 3

    def test_of_topic_filters(self) -> None:
        bus = InMemoryMessageBus()

        async def go() -> None:
            for topic in ("orders", "shipments", "orders"):
                await bus.publish(_message(topic))

        asyncio.run(go())
        assert len(bus.of_topic("orders")) == 2
        assert len(bus.of_topic("shipments")) == 1
        assert len(bus.of_topic("unknown")) == 0

    def test_clear_empties_bus(self) -> None:
        bus = InMemoryMessageBus()
        asyncio.run(bus.publish(_message()))
        bus.clear()
        assert bus.published == []

    def test_published_returns_copy(self) -> None:
        bus = InMemoryMessageBus()
        asyncio.run(bus.publish(_message()))
        copy = bus.published
        copy.clear()
        assert len(bus.published) == 1


# ---------------------------------------------------------------------------
# §36.3  InMemoryOutboxRepository
# ---------------------------------------------------------------------------


class TestInMemoryOutboxRepository:
    def test_save_and_get_pending(self) -> None:
        repo = InMemoryOutboxRepository()
        rec = _outbox_record()
        asyncio.run(repo.save(rec))
        pending = asyncio.run(repo.get_pending(limit=10))
        assert len(pending) == 1
        assert pending[0].topic == "orders"

    def test_pending_limit_respected(self) -> None:
        repo = InMemoryOutboxRepository()

        async def go() -> None:
            for _ in range(5):
                await repo.save(_outbox_record())

        asyncio.run(go())
        assert len(asyncio.run(repo.get_pending(limit=3))) == 3

    def test_mark_dispatched_removes_from_pending(self) -> None:
        repo = InMemoryOutboxRepository()
        rec = _outbox_record()

        async def go() -> None:
            await repo.save(rec)
            await repo.mark_dispatched(rec.id)

        asyncio.run(go())
        assert asyncio.run(repo.get_pending(limit=10)) == []

    def test_mark_dispatched_sets_status(self) -> None:
        repo = InMemoryOutboxRepository()
        rec = _outbox_record()

        async def go() -> None:
            await repo.save(rec)
            await repo.mark_dispatched(rec.id)

        asyncio.run(go())
        assert repo.all_records()[0].status == OutboxStatus.DISPATCHED

    def test_mark_failed_sets_status(self) -> None:
        repo = InMemoryOutboxRepository()
        rec = _outbox_record()

        async def go() -> None:
            await repo.save(rec)
            await repo.mark_failed(rec.id, error="timeout")

        asyncio.run(go())
        assert repo.all_records()[0].status == OutboxStatus.FAILED

    def test_all_records_returns_all(self) -> None:
        repo = InMemoryOutboxRepository()

        async def go() -> None:
            await repo.save(_outbox_record())
            await repo.save(_outbox_record())

        asyncio.run(go())
        assert len(repo.all_records()) == 2


# ---------------------------------------------------------------------------
# §36.4  InMemoryInboxRepository
# ---------------------------------------------------------------------------


class TestInMemoryInboxRepository:
    def test_save_and_get(self) -> None:
        repo = InMemoryInboxRepository()
        rec = _inbox_record("msg-42")

        async def go() -> InboxRecord | None:
            await repo.save(rec)
            return await repo.get("msg-42")

        result = asyncio.run(go())
        assert result is not None
        assert result.message_id == "msg-42"

    def test_get_missing_returns_none(self) -> None:
        repo = InMemoryInboxRepository()
        assert asyncio.run(repo.get("does-not-exist")) is None

    def test_mark_processed_updates_status(self) -> None:
        repo = InMemoryInboxRepository()
        rec = _inbox_record("m1")

        async def go() -> None:
            await repo.save(rec)
            await repo.mark_processed("m1")

        asyncio.run(go())
        assert repo.all_records()[0].status == InboxStatus.PROCESSED

    def test_all_records(self) -> None:
        repo = InMemoryInboxRepository()
        asyncio.run(repo.save(_inbox_record("a")))
        asyncio.run(repo.save(_inbox_record("b")))
        assert len(repo.all_records()) == 2


# ---------------------------------------------------------------------------
# §36.5  InMemoryIdempotencyStore
# ---------------------------------------------------------------------------


class TestInMemoryIdempotencyStore:
    def test_get_missing_returns_none(self) -> None:
        store = InMemoryIdempotencyStore()
        assert asyncio.run(store.get(_idempotency_key())) is None

    def test_save_and_get(self) -> None:
        store = InMemoryIdempotencyStore()
        key = _idempotency_key("save-op")
        rec = _idempotency_record(key)

        async def go() -> IdempotencyRecord | None:
            await store.save(key, rec)
            return await store.get(key)

        result = asyncio.run(go())
        assert result is not None
        assert result.status == "PROCESSING"

    def test_complete_sets_response(self) -> None:
        store = InMemoryIdempotencyStore()
        key = _idempotency_key("complete-op")
        rec = _idempotency_record(key)

        async def go() -> IdempotencyRecord | None:
            await store.save(key, rec)
            await store.complete(key, b"done")
            return await store.get(key)

        result = asyncio.run(go())
        assert result is not None
        assert result.response == b"done"
        assert result.status == "COMPLETED"

    def test_all_keys(self) -> None:
        store = InMemoryIdempotencyStore()

        async def go() -> None:
            for i in range(3):
                k = _idempotency_key(f"op-{i}")
                await store.save(k, _idempotency_record(k))

        asyncio.run(go())
        assert len(store.all_keys()) == 3


# ---------------------------------------------------------------------------
# §36.6  FakePolicyEngine
# ---------------------------------------------------------------------------


class TestFakePolicyEngine:
    def test_allow_by_default(self) -> None:
        engine = FakePolicyEngine()
        result = asyncio.run(engine.evaluate(_ctx("orders", "read")))
        assert result == PolicyDecision.ALLOW

    def test_deny_specific_resource_action(self) -> None:
        engine = FakePolicyEngine()
        engine.set("orders", "delete", PolicyDecision.DENY)
        assert asyncio.run(engine.evaluate(_ctx("orders", "read"))) == PolicyDecision.ALLOW
        assert asyncio.run(engine.evaluate(_ctx("orders", "delete"))) == PolicyDecision.DENY

    def test_deny_all(self) -> None:
        engine = FakePolicyEngine()
        engine.deny_all()
        assert asyncio.run(engine.evaluate(_ctx("any", "any"))) == PolicyDecision.DENY

    def test_allow_all_restores_default(self) -> None:
        engine = FakePolicyEngine()
        engine.deny_all()
        engine.allow_all()
        assert asyncio.run(engine.evaluate(_ctx("any", "any"))) == PolicyDecision.ALLOW

    def test_override_takes_precedence_over_deny_all(self) -> None:
        engine = FakePolicyEngine()
        engine.deny_all()
        engine.set("health", "read", PolicyDecision.ALLOW)
        assert asyncio.run(engine.evaluate(_ctx("health", "read"))) == PolicyDecision.ALLOW
        assert asyncio.run(engine.evaluate(_ctx("orders", "write"))) == PolicyDecision.DENY
