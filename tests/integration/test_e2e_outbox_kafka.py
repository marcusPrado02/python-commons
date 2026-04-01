"""T-01 — End-to-end integration test: command → outbox → Kafka → consumer → inbox deduplication.

This test exercises the full at-least-once delivery pipeline:

1. A command is dispatched; the handler records a domain event to the outbox.
2. ``KafkaOutboxDispatcher`` reads pending outbox entries and publishes them to Kafka.
3. ``KafkaConsumer`` receives the message and hands it to ``InboxProcessor``.
4. ``InboxProcessor`` de-duplicates via the ``InMemoryInboxStore`` (second delivery is no-op).
5. A duplicate re-delivery is detected and silently dropped.

Run with: pytest tests/integration/test_e2e_outbox_kafka.py -m integration -v

Requires Docker.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

import pytest
from testcontainers.kafka import KafkaContainer

from mp_commons.adapters.kafka import KafkaConsumer, KafkaOutboxDispatcher, KafkaProducer
from mp_commons.application.inbox import (
    InboxProcessor,
    InboxRecord,
    InboxStatus,
    InMemoryInboxStore,
)
from mp_commons.kernel.messaging import OutboxRecord, OutboxStatus
from mp_commons.testing.fakes.outbox import InMemoryOutboxRepository


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _run(coro: Any) -> Any:  # type: ignore[no-untyped-def]
    return asyncio.run(coro)


_TOPIC = "e2e-orders"


@pytest.fixture(scope="module")
def kafka_bootstrap() -> str:  # type: ignore[return]
    with KafkaContainer("confluentinc/cp-kafka:7.6.1") as kc:
        yield kc.get_bootstrap_server()


# ---------------------------------------------------------------------------
# Fake infrastructure
# ---------------------------------------------------------------------------


class _FakeOutboxRepo(InMemoryOutboxRepository):
    """Thin wrapper that surfaces dispatched list for assertions."""

    def __init__(self) -> None:
        super().__init__()
        self.dispatched: list[str] = []

    async def mark_dispatched(self, record_id: str) -> None:
        await super().mark_dispatched(record_id)
        self.dispatched.append(record_id)


class _RecordingCommandBus:
    """Captures InboxProcessor dispatched events for assertions."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []

    async def dispatch(self, event_type: str, payload: Any) -> None:
        self.calls.append((event_type, payload))


# ---------------------------------------------------------------------------
# T-01 — Full pipeline test
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestE2EOutboxKafkaPipeline:
    """Command → Outbox → Kafka → Consumer → Inbox deduplication."""

    def test_full_pipeline_single_message(self, kafka_bootstrap: str) -> None:
        outbox_repo = _FakeOutboxRepo()
        inbox_store = InMemoryInboxStore()
        bus = _RecordingCommandBus()

        order_id = str(uuid.uuid4())
        payload_dict = {"order_id": order_id, "customer_id": "cust-1"}

        # OutboxRecord.payload is bytes — JSON-encode the dict
        outbox_record = OutboxRecord(
            id=str(uuid.uuid4()),
            aggregate_id=order_id,
            event_type="OrderCreated",
            payload=json.dumps(payload_dict).encode(),
            topic=_TOPIC,
        )

        async def _run_test() -> None:
            await outbox_repo.save(outbox_record)

            # --- Step 2: Dispatch pending outbox entries to Kafka ---
            producer = KafkaProducer(bootstrap_servers=kafka_bootstrap)
            async with producer:
                dispatcher = KafkaOutboxDispatcher(bus=producer, repo=outbox_repo)
                dispatched_count = await dispatcher.dispatch_pending()
            assert dispatched_count == 1
            assert outbox_record.id in outbox_repo.dispatched

            # Verify the outbox record is now marked DISPATCHED
            records = outbox_repo.all_records()
            assert records[0].status == OutboxStatus.DISPATCHED

            # --- Step 3: Consumer reads the Kafka message ---
            # auto_offset_reset="earliest" ensures we pick up the message just published
            raw_msgs: list[Any] = []
            consumer = KafkaConsumer(
                bootstrap_servers=kafka_bootstrap,
                topics=[_TOPIC],
                group_id="e2e-test-group",
                auto_offset_reset="earliest",
            )
            async with consumer:
                async for msg in consumer:
                    raw_msgs.append(msg)
                    break  # only consume one message

            assert len(raw_msgs) == 1
            # KafkaConsumer yields raw aiokafka ConsumerRecord; payload is msg.value (bytes)
            received_payload = json.loads(raw_msgs[0].value)
            assert received_payload.get("order_id") == order_id

            # --- Step 4: InboxProcessor processes the message ---
            # InboxRecord from mp_commons.application.inbox has source/event_type/payload: Any
            inbox_id = str(uuid.uuid4())
            inbox_record = InboxRecord(
                id=inbox_id,
                source=_TOPIC,
                event_type="OrderCreated",
                payload=received_payload,
            )
            processor = InboxProcessor(store=inbox_store, command_bus=bus)
            result = await processor.process(inbox_record)
            assert result.status == InboxStatus.PROCESSED
            assert len(bus.calls) == 1
            assert bus.calls[0][0] == "OrderCreated"

            # --- Step 5: Duplicate delivery is de-duplicated ---
            # Same id as the first record — InboxProcessor deduplicates by record.id
            duplicate = InboxRecord(
                id=inbox_id,  # same id → triggers is_duplicate check
                source=_TOPIC,
                event_type="OrderCreated",
                payload=received_payload,
            )
            dup_result = await processor.process(duplicate)
            assert dup_result.status == InboxStatus.DUPLICATE
            # Bus should still have only 1 call — duplicate was dropped
            assert len(bus.calls) == 1

        _run(_run_test())
