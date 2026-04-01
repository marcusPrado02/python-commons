"""Unit tests for PubSubProducer and PubSubSubscriber (A-02)."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

import mp_commons.adapters.gcp_pubsub.messaging as _mod
from mp_commons.adapters.gcp_pubsub.messaging import PubSubProducer, PubSubSubscriber


class TestPubSubProducer:
    def _make_producer(self) -> tuple[PubSubProducer, MagicMock]:
        producer = PubSubProducer(project_id="my-proj", topic_id="orders")
        mock_publisher = MagicMock()
        mock_publisher.topic_path.return_value = "projects/my-proj/topics/orders"

        future = MagicMock()
        future.result.return_value = "msg-id-1"
        mock_publisher.publish.return_value = future

        producer._publisher = mock_publisher
        producer._topic_path = "projects/my-proj/topics/orders"
        return producer, mock_publisher

    @pytest.mark.asyncio
    async def test_send_returns_message_id(self):
        producer, publisher = self._make_producer()
        result = await producer.send({"event": "created"})
        assert result == "msg-id-1"

    @pytest.mark.asyncio
    async def test_send_serialises_to_json_bytes(self):
        producer, publisher = self._make_producer()
        await producer.send({"key": "value"})
        call_args = publisher.publish.call_args
        data = call_args[0][1]  # second positional arg is data
        assert json.loads(data) == {"key": "value"}

    @pytest.mark.asyncio
    async def test_send_passes_attributes(self):
        producer, publisher = self._make_producer()
        await producer.send({"k": "v"}, source="test")
        call_kwargs = publisher.publish.call_args[1]
        assert call_kwargs.get("source") == "test"

    @pytest.mark.asyncio
    async def test_send_batch_returns_all_ids(self):
        producer, publisher = self._make_producer()
        counter = 0

        async def fake_send(payload, **kwargs):
            nonlocal counter
            counter += 1
            return f"id-{counter}"

        producer.send = fake_send  # type: ignore[method-assign]
        results = await producer.send_batch([{"a": 1}, {"b": 2}])
        assert results == ["id-1", "id-2"]

    @pytest.mark.asyncio
    async def test_missing_pubsub_raises(self):
        producer = PubSubProducer(project_id="p", topic_id="t")
        with patch.object(_mod, "_require_pubsub", side_effect=ImportError("no gcp")):
            with pytest.raises(ImportError):
                await producer.__aenter__()


class TestPubSubSubscriber:
    def _make_subscriber(self, messages: list[dict]) -> tuple[PubSubSubscriber, MagicMock]:
        subscriber = PubSubSubscriber(project_id="my-proj", subscription_id="orders-sub")

        mock_sub_client = MagicMock()
        mock_sub_client.subscription_path.return_value = (
            "projects/my-proj/subscriptions/orders-sub"
        )
        mock_sub_client.acknowledge = MagicMock()

        received_msgs = []
        for i, payload in enumerate(messages):
            msg = MagicMock()
            msg.message.data = json.dumps(payload).encode()
            msg.ack_id = f"ack-{i}"
            received_msgs.append(msg)

        mock_response = MagicMock()
        mock_response.received_messages = received_msgs
        mock_sub_client.pull.return_value = mock_response

        subscriber._subscriber = mock_sub_client
        subscriber._subscription_path = "projects/my-proj/subscriptions/orders-sub"
        return subscriber, mock_sub_client

    @pytest.mark.asyncio
    async def test_pull_yields_decoded_payloads(self):
        subscriber, _ = self._make_subscriber([{"event": "A"}, {"event": "B"}])
        results: list = []
        async for msg in subscriber.pull():
            results.append(msg)
        assert len(results) == 2
        assert results[0]["event"] == "A"
        assert results[1]["event"] == "B"

    @pytest.mark.asyncio
    async def test_pull_acknowledges_messages(self):
        subscriber, mock_sub = self._make_subscriber([{"x": 1}])
        async for _ in subscriber.pull():
            pass
        mock_sub.acknowledge.assert_called_once()

    @pytest.mark.asyncio
    async def test_pull_empty_subscription(self):
        subscriber, _ = self._make_subscriber([])
        results: list = []
        async for msg in subscriber.pull():
            results.append(msg)
        assert results == []
