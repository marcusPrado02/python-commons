"""Unit tests for §74 – Inbox Pattern."""
import asyncio

import pytest

from mp_commons.application.inbox import (
    InboxProcessor,
    InboxRecord,
    InboxStatus,
    InMemoryInboxStore,
)


class _MockBus:
    def __init__(self, raise_on: str | None = None):
        self.dispatched: list[tuple[str, object]] = []
        self._raise_on = raise_on

    async def dispatch(self, event_type: str, payload: object) -> None:
        if self._raise_on and event_type == self._raise_on:
            raise ValueError(f"dispatch failed for {event_type}")
        self.dispatched.append((event_type, payload))


class TestInboxProcessor:
    def test_processes_new_record(self):
        store = InMemoryInboxStore()
        bus = _MockBus()
        processor = InboxProcessor(store, bus)
        record = InboxRecord(source="svc", event_type="OrderCreated", payload={"id": 1})
        result = asyncio.run(processor.process(record))
        assert result.status == InboxStatus.PROCESSED
        assert result.processed_at is not None
        assert len(bus.dispatched) == 1

    def test_duplicate_not_dispatched(self):
        store = InMemoryInboxStore()
        bus = _MockBus()
        processor = InboxProcessor(store, bus)
        record = InboxRecord(source="svc", event_type="OrderCreated", payload={})

        # Process once to mark PROCESSED
        asyncio.run(processor.process(record))
        bus.dispatched.clear()

        # Process again with same id – should be DUPLICATE
        result = asyncio.run(processor.process(record))
        assert result.status == InboxStatus.DUPLICATE
        assert len(bus.dispatched) == 0

    def test_failed_on_dispatch_exception(self):
        store = InMemoryInboxStore()
        bus = _MockBus(raise_on="BadEvent")
        processor = InboxProcessor(store, bus)
        record = InboxRecord(source="svc", event_type="BadEvent", payload={})
        result = asyncio.run(processor.process(record))
        assert result.status == InboxStatus.FAILED
        assert result.error is not None

    def test_is_duplicate_after_processed(self):
        store = InMemoryInboxStore()
        bus = _MockBus()
        processor = InboxProcessor(store, bus)
        record = InboxRecord(source="svc", event_type="Evt", payload={})
        asyncio.run(processor.process(record))
        assert asyncio.run(store.is_duplicate(record.id)) is True

    def test_different_ids_independent(self):
        store = InMemoryInboxStore()
        bus = _MockBus()
        processor = InboxProcessor(store, bus)
        r1 = InboxRecord(source="svc", event_type="Evt", payload={})
        r2 = InboxRecord(source="svc", event_type="Evt", payload={})
        asyncio.run(processor.process(r1))
        asyncio.run(processor.process(r2))
        assert len(bus.dispatched) == 2
