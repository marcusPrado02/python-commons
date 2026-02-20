"""Unit tests for kernel messaging ports."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from mp_commons.kernel.messaging import (
    DeadLetterEntry,
    DeadLetterStore,
    DeduplicationPolicy,
    IdempotencyKey,
    IdempotencyRecord,
    IdempotencyStore,
    InboxRecord,
    InboxRepository,
    InboxStatus,
    InboxStore,
    Message,
    MessageEnvelope,
    MessageHeaders,
    OutboxDispatcher,
    OutboxRecord,
    OutboxRepository,
    OutboxStatus,
    ScheduledMessage,
    ScheduledMessageStore,
)


# ---------------------------------------------------------------------------
# OutboxRecord lifecycle (5.2)
# ---------------------------------------------------------------------------


class TestOutboxRecord:
    def test_default_status_is_pending(self) -> None:
        r = OutboxRecord(event_type="OrderPlaced", topic="orders")
        assert r.status == OutboxStatus.PENDING

    def test_record_has_unique_id(self) -> None:
        r1 = OutboxRecord()
        r2 = OutboxRecord()
        assert r1.id != r2.id

    def test_retry_count_starts_at_zero(self) -> None:
        assert OutboxRecord().retry_count == 0


class InMemoryOutboxRepository(OutboxRepository):
    """In-memory stub for tests."""

    def __init__(self) -> None:
        self._records: dict[str, OutboxRecord] = {}

    async def save(self, record: OutboxRecord) -> None:
        self._records[record.id] = record

    async def get_pending(self, limit: int = 100) -> list[OutboxRecord]:
        return [
            r for r in self._records.values()
            if r.status == OutboxStatus.PENDING
        ][:limit]

    async def mark_dispatched(self, record_id: str) -> None:
        self._records[record_id].status = OutboxStatus.DISPATCHED
        self._records[record_id].dispatched_at = datetime.now(UTC)

    async def mark_failed(self, record_id: str, error: str) -> None:
        self._records[record_id].status = OutboxStatus.FAILED
        self._records[record_id].last_error = error


class TestOutboxRepository:
    def test_pending_then_dispatched(self) -> None:
        repo = InMemoryOutboxRepository()

        async def _run() -> None:
            rec = OutboxRecord(event_type="E", topic="t", payload=b"data")
            await repo.save(rec)
            pending = await repo.get_pending()
            assert len(pending) == 1
            assert pending[0].status == OutboxStatus.PENDING

            await repo.mark_dispatched(rec.id)
            pending_after = await repo.get_pending()
            assert len(pending_after) == 0
            assert repo._records[rec.id].status == OutboxStatus.DISPATCHED

        asyncio.run(_run())

    def test_mark_failed_sets_error(self) -> None:
        repo = InMemoryOutboxRepository()

        async def _run() -> None:
            rec = OutboxRecord(event_type="E", topic="t")
            await repo.save(rec)
            await repo.mark_failed(rec.id, "connection refused")
            r = repo._records[rec.id]
            assert r.status == OutboxStatus.FAILED
            assert r.last_error == "connection refused"

        asyncio.run(_run())

    def test_pending_limit(self) -> None:
        repo = InMemoryOutboxRepository()

        async def _run() -> None:
            for i in range(5):
                await repo.save(OutboxRecord(event_type=f"E{i}", topic="t"))
            pending = await repo.get_pending(limit=3)
            assert len(pending) == 3

        asyncio.run(_run())


# ---------------------------------------------------------------------------
# InboxRecord — duplicate rejection (5.4)
# ---------------------------------------------------------------------------


class InMemoryInboxRepository(InboxRepository):
    def __init__(self) -> None:
        self._records: dict[str, InboxRecord] = {}

    async def save(self, record: InboxRecord) -> None:
        self._records[record.id] = record

    async def find_by_message_id(self, message_id: str) -> InboxRecord | None:
        return next(
            (r for r in self._records.values() if r.message_id == message_id),
            None,
        )

    async def mark_processed(self, record_id: str) -> None:
        self._records[record_id].status = InboxStatus.PROCESSED
        self._records[record_id].processed_at = datetime.now(UTC)

    async def mark_failed(self, record_id: str, error: str) -> None:
        self._records[record_id].status = InboxStatus.FAILED
        self._records[record_id].error = error


class TestInboxRepository:
    def test_new_record_is_received(self) -> None:
        repo = InMemoryInboxRepository()

        async def _run() -> None:
            rec = InboxRecord(message_id="msg-1", topic="payments")
            await repo.save(rec)
            found = await repo.find_by_message_id("msg-1")
            assert found is not None
            assert found.status == InboxStatus.RECEIVED

        asyncio.run(_run())

    def test_duplicate_detection(self) -> None:
        repo = InMemoryInboxRepository()

        async def _run() -> None:
            rec = InboxRecord(message_id="msg-dup", topic="t")
            await repo.save(rec)
            await repo.mark_processed(rec.id)
            existing = await repo.find_by_message_id("msg-dup")
            # caller checks this to reject duplicates
            assert existing is not None
            assert existing.status == InboxStatus.PROCESSED

        asyncio.run(_run())

    def test_mark_failed(self) -> None:
        repo = InMemoryInboxRepository()

        async def _run() -> None:
            rec = InboxRecord(message_id="msg-fail", topic="t")
            await repo.save(rec)
            await repo.mark_failed(rec.id, "parse error")
            assert repo._records[rec.id].status == InboxStatus.FAILED
            assert repo._records[rec.id].error == "parse error"

        asyncio.run(_run())


# ---------------------------------------------------------------------------
# InboxStore — simplified Protocol (5.4)
# ---------------------------------------------------------------------------


class InMemoryInboxStore(InboxStore):
    def __init__(self) -> None:
        self._seen: set[str] = set()

    async def record(self, message_id: str) -> None:
        self._seen.add(message_id)

    async def has_been_processed(self, message_id: str) -> bool:
        return message_id in self._seen


class TestInboxStore:
    def test_new_message_not_processed(self) -> None:
        store = InMemoryInboxStore()
        result = asyncio.run(store.has_been_processed("new-msg"))
        assert result is False

    def test_records_message(self) -> None:
        store = InMemoryInboxStore()

        async def _run() -> None:
            await store.record("msg-1")
            assert await store.has_been_processed("msg-1") is True

        asyncio.run(_run())

    def test_different_ids_independent(self) -> None:
        store = InMemoryInboxStore()

        async def _run() -> None:
            await store.record("msg-a")
            assert await store.has_been_processed("msg-a") is True
            assert await store.has_been_processed("msg-b") is False

        asyncio.run(_run())


# ---------------------------------------------------------------------------
# MessageEnvelope (5.7)
# ---------------------------------------------------------------------------


class TestMessageEnvelope:
    def test_defaults(self) -> None:
        env = MessageEnvelope(topic="payments", payload=b'{"amount": 100}')
        assert env.topic == "payments"
        assert env.payload == b'{"amount": 100}'
        assert env.message_id  # auto-generated

    def test_with_headers(self) -> None:
        headers = MessageHeaders(correlation_id="corr-1", tenant_id="t-1")
        env = MessageEnvelope(topic="t", headers=headers)
        assert env.headers.correlation_id == "corr-1"
        assert env.headers.tenant_id == "t-1"

    def test_unique_ids(self) -> None:
        e1 = MessageEnvelope(topic="t")
        e2 = MessageEnvelope(topic="t")
        assert e1.message_id != e2.message_id

    def test_frozen(self) -> None:
        env = MessageEnvelope(topic="t")
        with pytest.raises((AttributeError, TypeError)):
            env.topic = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# DeadLetterStore (5.8)
# ---------------------------------------------------------------------------


class InMemoryDeadLetterStore(DeadLetterStore):
    def __init__(self) -> None:
        self._entries: list[DeadLetterEntry] = []

    async def push(self, message_id: str, payload: bytes, reason: str) -> None:
        entry = DeadLetterEntry(message_id=message_id, payload=payload, reason=reason)
        self._entries.append(entry)

    async def list(self, limit: int = 100) -> list[DeadLetterEntry]:
        return self._entries[:limit]

    async def replay(self, entry_id: str) -> None:
        for e in self._entries:
            if e.id == entry_id:
                e.replayed = True


class TestDeadLetterStore:
    def test_push_and_list(self) -> None:
        store = InMemoryDeadLetterStore()

        async def _run() -> None:
            await store.push("m-1", b"payload", "parse error")
            await store.push("m-2", b"data", "timeout")
            entries = await store.list()
            assert len(entries) == 2
            assert entries[0].reason == "parse error"

        asyncio.run(_run())

    def test_list_limit(self) -> None:
        store = InMemoryDeadLetterStore()

        async def _run() -> None:
            for i in range(5):
                await store.push(f"m-{i}", b"", "err")
            assert len(await store.list(limit=2)) == 2

        asyncio.run(_run())

    def test_replay_marks_entry(self) -> None:
        store = InMemoryDeadLetterStore()

        async def _run() -> None:
            await store.push("m-1", b"x", "err")
            entries = await store.list()
            entry_id = entries[0].id
            await store.replay(entry_id)
            assert store._entries[0].replayed is True

        asyncio.run(_run())


# ---------------------------------------------------------------------------
# ScheduledMessage (5.9)
# ---------------------------------------------------------------------------


class InMemoryScheduledStore(ScheduledMessageStore):
    def __init__(self) -> None:
        self._messages: list[ScheduledMessage] = []

    async def schedule(self, message: ScheduledMessage) -> None:
        self._messages.append(message)

    async def due(self, now: datetime, limit: int = 100) -> list[ScheduledMessage]:
        return [m for m in self._messages if m.deliver_at <= now][:limit]

    async def delete(self, message_id: str) -> None:
        self._messages = [m for m in self._messages if m.id != message_id]


class TestScheduledMessage:
    def test_schedule_and_due(self) -> None:
        store = InMemoryScheduledStore()
        now = datetime.now(UTC)

        async def _run() -> None:
            past = ScheduledMessage(topic="t", payload=b"p", deliver_at=now - timedelta(minutes=1))
            future = ScheduledMessage(topic="t", payload=b"q", deliver_at=now + timedelta(hours=1))
            await store.schedule(past)
            await store.schedule(future)
            due = await store.due(now)
            assert len(due) == 1
            assert due[0].payload == b"p"

        asyncio.run(_run())

    def test_delete_removes_message(self) -> None:
        store = InMemoryScheduledStore()
        now = datetime.now(UTC)

        async def _run() -> None:
            msg = ScheduledMessage(topic="t", deliver_at=now - timedelta(seconds=1))
            await store.schedule(msg)
            await store.delete(msg.id)
            assert await store.due(now) == []

        asyncio.run(_run())

    def test_frozen(self) -> None:
        msg = ScheduledMessage(topic="t")
        with pytest.raises((AttributeError, TypeError)):
            msg.topic = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Public surface smoke test
# ---------------------------------------------------------------------------


class TestPublicReExports:
    def test_all_symbols_importable(self) -> None:
        import importlib

        mod = importlib.import_module("mp_commons.kernel.messaging")
        for name in mod.__all__:
            assert hasattr(mod, name), f"{name!r} missing from mp_commons.kernel.messaging"
