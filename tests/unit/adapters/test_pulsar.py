"""Unit tests for the Pulsar adapter (§57)."""

from __future__ import annotations

import asyncio
import sys
import types
from unittest.mock import AsyncMock, MagicMock

import pytest

# ---------------------------------------------------------------------------
# Stub the pulsar package so tests run without the real library
# ---------------------------------------------------------------------------

_pulsar_mod = types.ModuleType("pulsar")

_fake_client_class = MagicMock(name="Client")
_pulsar_mod.Client = _fake_client_class  # type: ignore[attr-defined]

_pulsar_mod.ConsumerType = MagicMock()  # type: ignore[attr-defined]

_timeout_exc_class = type("Timeout", (Exception,), {})
_pulsar_mod.Timeout = _timeout_exc_class  # type: ignore[attr-defined]

sys.modules.setdefault("pulsar", _pulsar_mod)

from mp_commons.adapters.pulsar.messaging import (
    PulsarConsumer,
    PulsarOutboxDispatcher,
    PulsarProducer,
)

# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _make_producer() -> tuple[PulsarProducer, MagicMock, MagicMock]:
    """Return (PulsarProducer, mock_client, mock_topic_producer)."""
    topic_producer = MagicMock()
    topic_producer.send = MagicMock(return_value=None)
    topic_producer.flush = MagicMock()
    topic_producer.close = MagicMock()

    mock_client = MagicMock()
    mock_client.create_producer = MagicMock(return_value=topic_producer)
    mock_client.close = MagicMock()

    _fake_client_class.return_value = mock_client

    prod = PulsarProducer.__new__(PulsarProducer)
    prod._service_url = "pulsar://localhost:6650"
    prod._client_kwargs = {}
    prod._client = mock_client
    prod._producers = {}

    return prod, mock_client, topic_producer


# ---------------------------------------------------------------------------
# PulsarProducer
# ---------------------------------------------------------------------------


def test_producer_connect_creates_client():
    prod = PulsarProducer.__new__(PulsarProducer)
    prod._service_url = "pulsar://localhost:6650"
    prod._client_kwargs = {}
    prod._client = None
    prod._producers = {}

    mock_client = MagicMock()
    _fake_client_class.return_value = mock_client

    asyncio.run(prod.connect())
    assert prod._client is mock_client


def test_producer_publish_sends_payload():
    from mp_commons.kernel.messaging.message import Message

    prod, _mock_client, topic_producer = _make_producer()

    class _TestEvent(Message):
        topic = "test.events"

    msg = _TestEvent(id="1")
    asyncio.run(prod.publish(msg))

    topic_producer.send.assert_called_once()
    sent_payload = topic_producer.send.call_args[0][0]
    assert b"1" in sent_payload  # ID present in JSON payload


def test_producer_close():
    prod, mock_client, topic_producer = _make_producer()
    # Pre-register a producer
    prod._producers["t"] = topic_producer

    prod.close()
    topic_producer.close.assert_called()
    mock_client.close.assert_called()
    assert prod._client is None


def test_producer_start_stop_lifecycle():
    prod = PulsarProducer.__new__(PulsarProducer)
    prod._service_url = "pulsar://localhost"
    prod._client_kwargs = {}
    prod._client = None
    prod._producers = {}

    mock_client = MagicMock()
    mock_client.close = MagicMock()
    _fake_client_class.return_value = mock_client

    async def run():
        async with prod:
            assert prod._client is not None

    asyncio.run(run())
    mock_client.close.assert_called()


# ---------------------------------------------------------------------------
# PulsarConsumer
# ---------------------------------------------------------------------------


def test_consumer_receives_message():
    mock_msg = MagicMock()
    mock_consumer = MagicMock()
    mock_consumer.receive = MagicMock(return_value=mock_msg)

    mock_client = MagicMock()
    mock_client.subscribe = MagicMock(return_value=mock_consumer)

    consumer = PulsarConsumer.__new__(PulsarConsumer)
    consumer._service_url = "pulsar://localhost"
    consumer._topic = "t"
    consumer._subscription = "sub"
    consumer._client = mock_client
    consumer._consumer = mock_consumer

    result = asyncio.run(consumer.__anext__())
    assert result is mock_msg


def test_consumer_stop_on_timeout():
    mock_consumer = MagicMock()
    mock_consumer.receive = MagicMock(side_effect=_timeout_exc_class("Timeout"))

    consumer = PulsarConsumer.__new__(PulsarConsumer)
    consumer._consumer = mock_consumer

    with pytest.raises(StopAsyncIteration):
        asyncio.run(consumer.__anext__())


def test_consumer_ack():
    mock_consumer = MagicMock()
    mock_consumer.acknowledge = MagicMock()

    consumer = PulsarConsumer.__new__(PulsarConsumer)
    consumer._consumer = mock_consumer

    msg = MagicMock()
    asyncio.run(consumer.ack(msg))
    mock_consumer.acknowledge.assert_called_once_with(msg)


# ---------------------------------------------------------------------------
# PulsarOutboxDispatcher
# ---------------------------------------------------------------------------


def test_dispatcher_publishes_and_marks_dispatched():
    from mp_commons.kernel.messaging.outbox import OutboxRecord

    record = OutboxRecord(
        id="r1",
        topic="orders",
        event_type="OrderCreated",
        aggregate_id="o1",
        aggregate_type="Order",
        payload=b'{"id":"o1"}',
    )

    prod, _mock_client, _topic_producer = _make_producer()
    repo = MagicMock()
    repo.get_pending = AsyncMock(return_value=[record])
    repo.mark_dispatched = AsyncMock()
    repo.mark_failed = AsyncMock()

    dispatcher = PulsarOutboxDispatcher(prod, repo)
    count = asyncio.run(dispatcher.dispatch_pending())

    assert count == 1
    repo.mark_dispatched.assert_called_once_with("r1")


def test_dispatcher_marks_failed_on_error():
    from mp_commons.kernel.messaging.outbox import OutboxRecord

    record = OutboxRecord(
        id="r1",
        topic="orders",
        event_type="E",
        aggregate_id="1",
        aggregate_type="T",
        payload=b"data",
    )

    prod, _mock_client, topic_producer = _make_producer()
    topic_producer.send = MagicMock(side_effect=Exception("broker down"))
    repo = MagicMock()
    repo.get_pending = AsyncMock(return_value=[record])
    repo.mark_dispatched = AsyncMock()
    repo.mark_failed = AsyncMock()

    dispatcher = PulsarOutboxDispatcher(prod, repo)
    count = asyncio.run(dispatcher.dispatch_pending())

    assert count == 0
    repo.mark_failed.assert_called_once()
