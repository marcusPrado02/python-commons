"""Unit tests for Kafka adapter – §29.1–29.4 (mocked, no aiokafka required)."""
from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from mp_commons.adapters.kafka.serializer import KafkaMessageSerializer
from mp_commons.adapters.kafka.producer import KafkaProducer
from mp_commons.adapters.kafka.consumer import KafkaConsumer
from mp_commons.adapters.kafka.outbox_dispatcher import KafkaOutboxDispatcher
from mp_commons.kernel.messaging import Message, MessageHeaders
from mp_commons.kernel.messaging.outbox import OutboxRecord


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_aiokafka_producer():
    """Return (mock_module, mock_producer_instance)."""
    mock_prod = MagicMock()
    mock_prod.start = AsyncMock()
    mock_prod.stop = AsyncMock()
    mock_prod.send = AsyncMock()
    mock_ak = MagicMock()
    mock_ak.AIOKafkaProducer.return_value = mock_prod
    return mock_ak, mock_prod


def _mock_aiokafka_consumer():
    """Return (mock_module, mock_consumer_instance)."""
    mock_cons = MagicMock()
    mock_cons.start = AsyncMock()
    mock_cons.stop = AsyncMock()
    mock_ak = MagicMock()
    mock_ak.AIOKafkaConsumer.return_value = mock_cons
    return mock_ak, mock_cons


def _make_producer(bootstrap: str = "localhost:9092") -> tuple[KafkaProducer, MagicMock]:
    mock_ak, mock_prod = _mock_aiokafka_producer()
    with patch("mp_commons.adapters.kafka.producer._require_aiokafka", return_value=mock_ak):
        producer = KafkaProducer(bootstrap)
    return producer, mock_prod


def _make_consumer(topics: list[str] | None = None) -> tuple[KafkaConsumer, MagicMock]:
    mock_ak, mock_cons = _mock_aiokafka_consumer()
    with patch("mp_commons.adapters.kafka.consumer._require_aiokafka", return_value=mock_ak):
        consumer = KafkaConsumer("localhost:9092", group_id="grp", topics=topics or ["orders"])
    return consumer, mock_cons


# ===========================================================================
# §29.3 – KafkaMessageSerializer
# ===========================================================================

class TestKafkaMessageSerializer:
    def test_serialize_dict_returns_bytes(self):
        ser = KafkaMessageSerializer()
        result = ser.serialize({"key": "value"})
        assert isinstance(result, bytes)
        assert json.loads(result) == {"key": "value"}

    def test_serialize_bytes_passthrough(self):
        ser = KafkaMessageSerializer()
        raw = b"already bytes"
        assert ser.serialize(raw) is raw

    def test_serialize_non_serializable_falls_back_to_str(self):
        from datetime import date

        ser = KafkaMessageSerializer()
        result = ser.serialize({"d": date(2024, 1, 1)})
        assert b"2024-01-01" in result

    def test_deserialize_plain_dict(self):
        ser = KafkaMessageSerializer()
        data = json.dumps({"x": 1}).encode()
        assert ser.deserialize(data, dict) == {"x": 1}

    def test_deserialize_calls_model_validate_when_available(self):
        ser = KafkaMessageSerializer()
        mock_cls = MagicMock()
        mock_cls.model_validate.return_value = "parsed"
        data = json.dumps({"a": 1}).encode()
        result = ser.deserialize(data, mock_cls)
        mock_cls.model_validate.assert_called_once_with({"a": 1})
        assert result == "parsed"

    def test_serialize_list(self):
        ser = KafkaMessageSerializer()
        result = ser.serialize([1, 2, 3])
        assert json.loads(result) == [1, 2, 3]

    def test_serialize_string(self):
        ser = KafkaMessageSerializer()
        result = ser.serialize("hello")
        assert result == b'"hello"'


# ===========================================================================
# §29.1 – KafkaProducer
# ===========================================================================

class TestKafkaProducerImportError:
    def test_raises_import_error_without_lib(self):
        with patch(
            "mp_commons.adapters.kafka.producer._require_aiokafka",
            side_effect=ImportError("mp-commons[kafka]"),
        ):
            with pytest.raises(ImportError, match="kafka"):
                KafkaProducer("localhost:9092")


class TestKafkaProducer:
    def test_start_calls_producer_start(self):
        producer, mock_prod = _make_producer()
        asyncio.run(producer.start())
        mock_prod.start.assert_called_once()
        assert producer._started is True

    def test_stop_calls_producer_stop(self):
        producer, mock_prod = _make_producer()
        asyncio.run(producer.stop())
        mock_prod.stop.assert_called_once()
        assert producer._started is False

    def test_publish_calls_send_with_correct_topic(self):
        producer, mock_prod = _make_producer()
        producer._started = True
        msg = Message(id="msg-1", topic="orders", payload={"order": 1})
        asyncio.run(producer.publish(msg))
        mock_prod.send.assert_called_once()
        assert mock_prod.send.call_args.kwargs["topic"] == "orders"

    def test_publish_sends_message_id_as_key(self):
        producer, mock_prod = _make_producer()
        producer._started = True
        msg = Message(id="abc-123", topic="t", payload={})
        asyncio.run(producer.publish(msg))
        assert mock_prod.send.call_args.kwargs["key"] == b"abc-123"

    def test_publish_serializes_payload_as_json(self):
        producer, mock_prod = _make_producer()
        producer._started = True
        msg = Message(topic="t", payload={"x": 42})
        asyncio.run(producer.publish(msg))
        sent_value = mock_prod.send.call_args.kwargs["value"]
        assert json.loads(sent_value) == {"x": 42}

    def test_publish_includes_correlation_id_in_headers(self):
        producer, mock_prod = _make_producer()
        producer._started = True
        msg = Message(
            topic="t",
            payload={},
            headers=MessageHeaders(correlation_id="corr-123"),
        )
        asyncio.run(producer.publish(msg))
        headers = dict(mock_prod.send.call_args.kwargs["headers"])
        assert headers.get("correlation-id") == b"corr-123"

    def test_publish_includes_extra_headers(self):
        producer, mock_prod = _make_producer()
        producer._started = True
        msg = Message(
            topic="t",
            payload={},
            headers=MessageHeaders(extra={"x-tenant": "acme"}),
        )
        asyncio.run(producer.publish(msg))
        headers = dict(mock_prod.send.call_args.kwargs["headers"])
        assert headers.get("x-tenant") == b"acme"

    def test_publish_auto_starts_if_not_started(self):
        producer, mock_prod = _make_producer()
        assert producer._started is False
        msg = Message(topic="t", payload={})
        asyncio.run(producer.publish(msg))
        mock_prod.start.assert_called_once()

    def test_publish_batch_sends_all_messages(self):
        producer, mock_prod = _make_producer()
        producer._started = True
        msgs = [Message(topic="t", payload={"i": i}) for i in range(3)]
        asyncio.run(producer.publish_batch(msgs))
        assert mock_prod.send.call_count == 3

    def test_publish_batch_empty_list(self):
        producer, mock_prod = _make_producer()
        producer._started = True
        asyncio.run(producer.publish_batch([]))
        mock_prod.send.assert_not_called()

    def test_context_manager_starts_and_stops(self):
        producer, mock_prod = _make_producer()

        async def run():
            async with producer:
                pass

        asyncio.run(run())
        mock_prod.start.assert_called_once()
        mock_prod.stop.assert_called_once()

    def test_custom_bootstrap_servers_passed_to_aiokafka(self):
        mock_ak, _ = _mock_aiokafka_producer()
        with patch("mp_commons.adapters.kafka.producer._require_aiokafka", return_value=mock_ak):
            KafkaProducer("broker1:9092,broker2:9092")
        mock_ak.AIOKafkaProducer.assert_called_once_with(
            bootstrap_servers="broker1:9092,broker2:9092"
        )


# ===========================================================================
# §29.2 – KafkaConsumer
# ===========================================================================

class TestKafkaConsumerImportError:
    def test_raises_import_error_without_lib(self):
        with patch(
            "mp_commons.adapters.kafka.consumer._require_aiokafka",
            side_effect=ImportError("mp-commons[kafka]"),
        ):
            with pytest.raises(ImportError, match="kafka"):
                KafkaConsumer("localhost:9092", group_id="g1", topics=["t1"])


class TestKafkaConsumer:
    def test_start_calls_consumer_start(self):
        consumer, mock_cons = _make_consumer()
        asyncio.run(consumer.start())
        mock_cons.start.assert_called_once()

    def test_stop_calls_consumer_stop(self):
        consumer, mock_cons = _make_consumer()
        asyncio.run(consumer.stop())
        mock_cons.stop.assert_called_once()

    def test_context_manager_calls_start_and_stop(self):
        consumer, mock_cons = _make_consumer()

        async def run():
            async with consumer:
                pass

        asyncio.run(run())
        mock_cons.start.assert_called_once()
        mock_cons.stop.assert_called_once()

    def test_subscribers_for_multiple_topics(self):
        mock_ak, mock_cons = _mock_aiokafka_consumer()
        with patch("mp_commons.adapters.kafka.consumer._require_aiokafka", return_value=mock_ak):
            KafkaConsumer("localhost:9092", group_id="g", topics=["t1", "t2", "t3"])
        # AIOKafkaConsumer(*topics, ...) – topics passed as positional args
        call_args = mock_ak.AIOKafkaConsumer.call_args
        assert "t1" in call_args.args
        assert "t2" in call_args.args
        assert "t3" in call_args.args

    def test_group_id_passed_to_aiokafka(self):
        mock_ak, _ = _mock_aiokafka_consumer()
        with patch("mp_commons.adapters.kafka.consumer._require_aiokafka", return_value=mock_ak):
            KafkaConsumer("localhost:9092", group_id="my-group", topics=["t"])
        kwargs = mock_ak.AIOKafkaConsumer.call_args.kwargs
        assert kwargs["group_id"] == "my-group"


# ===========================================================================
# §29.4 – KafkaOutboxDispatcher
# ===========================================================================

def _make_dispatcher(records: list[OutboxRecord]):
    mock_ak, mock_prod = _mock_aiokafka_producer()
    with patch("mp_commons.adapters.kafka.producer._require_aiokafka", return_value=mock_ak):
        bus = KafkaProducer("localhost:9092")
    bus._started = True

    mock_repo = MagicMock()
    mock_repo.get_pending = AsyncMock(return_value=records)
    mock_repo.mark_dispatched = AsyncMock()
    mock_repo.mark_failed = AsyncMock()

    dispatcher = KafkaOutboxDispatcher(bus=bus, repo=mock_repo)
    return dispatcher, mock_repo, mock_prod


class TestKafkaOutboxDispatcher:
    def test_dispatch_empty_returns_zero(self):
        dispatcher, _, _ = _make_dispatcher([])
        result = asyncio.run(dispatcher.dispatch_pending())
        assert result == 0

    def test_dispatch_returns_count_of_dispatched(self):
        records = [OutboxRecord(id=f"r{i}", topic="orders", payload=b"{}") for i in range(3)]
        dispatcher, _, _ = _make_dispatcher(records)
        result = asyncio.run(dispatcher.dispatch_pending())
        assert result == 3

    def test_dispatch_calls_publish_for_each_record(self):
        records = [OutboxRecord(id="r1", topic="orders", payload=b'{"x":1}')]
        dispatcher, _, mock_prod = _make_dispatcher(records)
        asyncio.run(dispatcher.dispatch_pending())
        mock_prod.send.assert_called_once()
        assert mock_prod.send.call_args.kwargs["topic"] == "orders"

    def test_dispatch_calls_mark_dispatched(self):
        records = [OutboxRecord(id="r1", topic="orders", payload=b"{}")]
        dispatcher, mock_repo, _ = _make_dispatcher(records)
        asyncio.run(dispatcher.dispatch_pending())
        mock_repo.mark_dispatched.assert_called_once_with("r1")

    def test_dispatch_error_calls_mark_failed(self):
        records = [OutboxRecord(id="r1", topic="orders", payload=b"{}")]
        dispatcher, mock_repo, mock_prod = _make_dispatcher(records)
        mock_prod.send.side_effect = RuntimeError("broker down")
        result = asyncio.run(dispatcher.dispatch_pending())
        assert result == 0
        mock_repo.mark_failed.assert_called_once()
        args = mock_repo.mark_failed.call_args.args
        assert args[0] == "r1"
        assert "broker down" in args[1]

    def test_dispatch_continues_after_error(self):
        records = [
            OutboxRecord(id="r1", topic="t", payload=b"{}"),
            OutboxRecord(id="r2", topic="t", payload=b"{}"),
        ]
        dispatcher, mock_repo, mock_prod = _make_dispatcher(records)
        # fail only first send
        mock_prod.send.side_effect = [RuntimeError("oops"), None]
        result = asyncio.run(dispatcher.dispatch_pending())
        assert result == 1
        mock_repo.mark_failed.assert_called_once_with("r1", "oops")
        mock_repo.mark_dispatched.assert_called_once_with("r2")

    def test_dispatch_passes_correlation_id_from_headers(self):
        records = [
            OutboxRecord(
                id="r1",
                topic="orders",
                payload=b"{}",
                headers={"correlation-id": "corr-99"},
            )
        ]
        dispatcher, _, mock_prod = _make_dispatcher(records)
        asyncio.run(dispatcher.dispatch_pending())
        headers = dict(mock_prod.send.call_args.kwargs["headers"])
        assert headers.get("correlation-id") == b"corr-99"

    def test_dispatch_uses_record_id_as_message_id(self):
        records = [OutboxRecord(id="fixed-id", topic="t", payload=b"{}")]
        dispatcher, _, mock_prod = _make_dispatcher(records)
        asyncio.run(dispatcher.dispatch_pending())
        assert mock_prod.send.call_args.kwargs["key"] == b"fixed-id"
