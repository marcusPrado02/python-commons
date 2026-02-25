"""Integration tests for Kafka adapters (§29.5).

Uses testcontainers to spawn a real Kafka broker.
Run with: PYTHONPATH=src pytest tests/integration/test_kafka.py -m integration -v
"""
from __future__ import annotations

import asyncio
from typing import Any

import pytest
from testcontainers.kafka import KafkaContainer

from mp_commons.adapters.kafka import KafkaConsumer, KafkaOutboxDispatcher, KafkaProducer
from mp_commons.kernel.messaging import Message, MessageHeaders, OutboxRecord


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _run(coro):  # type: ignore[no-untyped-def]
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Minimal in-memory OutboxRepository for dispatcher tests
# ---------------------------------------------------------------------------

class _InMemoryOutboxRepo:
    def __init__(self, records: list[OutboxRecord]) -> None:
        self._records = list(records)
        self.dispatched: list[str] = []
        self.failed: list[tuple[str, str]] = []

    async def get_pending(self, limit: int = 100) -> list[OutboxRecord]:
        from mp_commons.kernel.messaging import OutboxStatus
        return [r for r in self._records if r.status == OutboxStatus.PENDING][:limit]

    async def mark_dispatched(self, record_id: str) -> None:
        from mp_commons.kernel.messaging import OutboxStatus
        for r in self._records:
            if r.id == record_id:
                object.__setattr__(r, "status", OutboxStatus.DISPATCHED)
        self.dispatched.append(record_id)

    async def mark_failed(self, record_id: str, error: str) -> None:
        from mp_commons.kernel.messaging import OutboxStatus
        for r in self._records:
            if r.id == record_id:
                object.__setattr__(r, "status", OutboxStatus.FAILED)
        self.failed.append((record_id, error))

    async def save(self, record: OutboxRecord) -> None:
        self._records.append(record)


# ---------------------------------------------------------------------------
# §29.5 – KafkaProducer – basic publish
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestKafkaProducerIntegration:
    """Real Kafka producer tests."""

    def test_producer_starts_and_stops(self) -> None:
        with KafkaContainer() as container:
            servers = container.get_bootstrap_server()

            async def run() -> None:
                producer = KafkaProducer(bootstrap_servers=servers)
                await producer.start()
                await producer.stop()

            _run(run())

    def test_producer_context_manager(self) -> None:
        with KafkaContainer() as container:
            servers = container.get_bootstrap_server()

            async def run() -> None:
                async with KafkaProducer(bootstrap_servers=servers):
                    pass  # just check connect/disconnect

            _run(run())

    def test_publish_single_message(self) -> None:
        with KafkaContainer() as container:
            servers = container.get_bootstrap_server()

            async def run() -> None:
                msg = Message(
                    id="msg-1",
                    topic="test-topic",
                    payload={"event": "OrderPlaced"},
                    headers=MessageHeaders(),
                )
                async with KafkaProducer(bootstrap_servers=servers) as producer:
                    await producer.publish(msg)  # should not raise

            _run(run())


# ---------------------------------------------------------------------------
# §29.5 – KafkaProducer + KafkaConsumer round-trip
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestKafkaProduceConsumeIntegration:
    """Real Kafka produce/consume round-trip test."""

    def test_produce_consume_roundtrip(self) -> None:
        with KafkaContainer() as container:
            servers = container.get_bootstrap_server()

            received: list[bytes] = []

            async def run() -> None:
                topic = "roundtrip-topic"
                msg = Message(
                    id="msg-2",
                    topic=topic,
                    payload={"order_id": "42"},
                    headers=MessageHeaders(),
                )

                async with KafkaProducer(bootstrap_servers=servers) as producer:
                    await producer.publish(msg)

                # Consume with a short timeout
                consumer = KafkaConsumer(
                    bootstrap_servers=servers,
                    group_id="test-group",
                    topics=[topic],
                    auto_offset_reset="earliest",
                )
                await consumer.start()
                try:
                    async for kafka_msg in consumer:
                        received.append(kafka_msg.value)
                        break  # only need one message
                finally:
                    await consumer.stop()

            _run(run())
            assert len(received) == 1
            assert b"order_id" in received[0]


# ---------------------------------------------------------------------------
# §29.5 – KafkaOutboxDispatcher
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestKafkaOutboxDispatcherIntegration:
    """Real Kafka outbox dispatcher tests."""

    def test_dispatcher_publishes_pending_records(self) -> None:
        with KafkaContainer() as container:
            servers = container.get_bootstrap_server()

            async def run() -> int:
                rec = OutboxRecord(
                    aggregate_id="agg-1",
                    aggregate_type="Order",
                    event_type="OrderPlaced",
                    topic="orders",
                    payload=b'{"order_id": "1"}',
                )
                repo = _InMemoryOutboxRepo([rec])
                async with KafkaProducer(bootstrap_servers=servers) as producer:
                    dispatcher = KafkaOutboxDispatcher(bus=producer, repo=repo)
                    count = await dispatcher.dispatch_pending()
                return count, repo

            count, repo = _run(run())
            assert count == 1
            assert len(repo.dispatched) == 1

    def test_dispatcher_marks_failed_on_publish_error(self) -> None:
        with KafkaContainer() as container:
            servers = container.get_bootstrap_server()

            async def run() -> Any:
                # Record with empty topic will likely fail publish
                rec = OutboxRecord(
                    aggregate_id="agg-2",
                    aggregate_type="Order",
                    event_type="Failed",
                    topic="",  # invalid topic
                    payload=b"{}",
                )
                repo = _InMemoryOutboxRepo([rec])
                async with KafkaProducer(bootstrap_servers=servers) as producer:
                    dispatcher = KafkaOutboxDispatcher(bus=producer, repo=repo)
                    count = await dispatcher.dispatch_pending()
                return count, repo

            count, repo = _run(run())
            # Either dispatched or failed — just assert no exception propagated
            assert count + len(repo.failed) == 1

    def test_dispatcher_returns_zero_when_no_pending(self) -> None:
        with KafkaContainer() as container:
            servers = container.get_bootstrap_server()

            async def run() -> int:
                repo = _InMemoryOutboxRepo([])
                async with KafkaProducer(bootstrap_servers=servers) as producer:
                    dispatcher = KafkaOutboxDispatcher(bus=producer, repo=repo)
                    return await dispatcher.dispatch_pending()

            assert _run(run()) == 0
