"""Unit tests for RabbitMQ adapter – §31.1–31.2 (mocked, no aio-pika required)."""
from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mp_commons.adapters.rabbitmq.bus import RabbitMQMessageBus
from mp_commons.kernel.messaging import Message, MessageHeaders
from mp_commons.resilience.retry.policy import RetryPolicy
from mp_commons.resilience.retry.backoff import ConstantBackoff
from mp_commons.resilience.retry.jitter import NoJitter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_aio_pika():
    mock_exchange = MagicMock()
    mock_exchange.publish = AsyncMock()

    mock_channel = MagicMock()
    mock_channel.default_exchange = mock_exchange

    mock_connection = MagicMock()
    mock_connection.channel = AsyncMock(return_value=mock_channel)
    mock_connection.close = AsyncMock()

    mock_ap = MagicMock()
    mock_ap.connect_robust = AsyncMock(return_value=mock_connection)
    mock_ap.Message = MagicMock(
        side_effect=lambda body, headers: MagicMock(body=body, headers=headers)
    )
    return mock_ap, mock_connection, mock_channel, mock_exchange


# ===========================================================================
# Import guard
# ===========================================================================

class TestRabbitMQImportError:
    def test_raises_import_error_without_lib(self):
        with patch(
            "mp_commons.adapters.rabbitmq.bus._require_aio_pika",
            side_effect=ImportError("mp-commons[rabbitmq]"),
        ):
            with pytest.raises(ImportError, match="rabbitmq"):
                RabbitMQMessageBus()


# ===========================================================================
# §31.1 – RabbitMQMessageBus core
# ===========================================================================

class TestRabbitMQMessageBusConnect:
    def setup_method(self):
        self.mock_ap, self.mock_conn, self.mock_ch, self.mock_ex = _make_mock_aio_pika()
        self._patcher = patch(
            "mp_commons.adapters.rabbitmq.bus._require_aio_pika",
            return_value=self.mock_ap,
        )
        self._patcher.start()
        self.bus = RabbitMQMessageBus()

    def teardown_method(self):
        self._patcher.stop()

    def test_connect_calls_connect_robust(self):
        asyncio.run(self.bus.connect())
        self.mock_ap.connect_robust.assert_called_once_with("amqp://guest:guest@localhost/")

    def test_connect_opens_channel(self):
        asyncio.run(self.bus.connect())
        self.mock_conn.channel.assert_called_once()
        assert self.bus._channel is self.mock_ch

    def test_connect_with_custom_url(self):
        self.bus._url = "amqp://admin:pw@broker:5672/vhost"
        asyncio.run(self.bus.connect())
        self.mock_ap.connect_robust.assert_called_once_with("amqp://admin:pw@broker:5672/vhost")

    def test_close_calls_connection_close(self):
        asyncio.run(self.bus.connect())
        asyncio.run(self.bus.close())
        self.mock_conn.close.assert_called_once()

    def test_close_without_connect_is_noop(self):
        asyncio.run(self.bus.close())
        self.mock_conn.close.assert_not_called()

    def test_context_manager_connects_and_closes(self):
        async def run():
            async with self.bus:
                pass
        asyncio.run(run())
        self.mock_ap.connect_robust.assert_called_once()
        self.mock_conn.close.assert_called_once()


class TestRabbitMQMessageBusPublish:
    def setup_method(self):
        self.mock_ap, self.mock_conn, self.mock_ch, self.mock_ex = _make_mock_aio_pika()
        self._patcher = patch(
            "mp_commons.adapters.rabbitmq.bus._require_aio_pika",
            return_value=self.mock_ap,
        )
        self._patcher.start()
        self.bus = RabbitMQMessageBus()

    def teardown_method(self):
        self._patcher.stop()

    def test_publish_calls_exchange_publish(self):
        asyncio.run(self.bus.connect())
        msg = Message(topic="orders", payload={"id": 1})
        asyncio.run(self.bus.publish(msg))
        self.mock_ex.publish.assert_called_once()

    def test_publish_uses_topic_as_routing_key(self):
        asyncio.run(self.bus.connect())
        msg = Message(topic="payments.created", payload={})
        asyncio.run(self.bus.publish(msg))
        assert self.mock_ex.publish.call_args.kwargs["routing_key"] == "payments.created"

    def test_publish_serializes_payload_as_json(self):
        asyncio.run(self.bus.connect())
        msg = Message(topic="t", payload={"x": 99})
        asyncio.run(self.bus.publish(msg))
        aio_msg_body = self.mock_ap.Message.call_args.kwargs["body"]
        assert json.loads(aio_msg_body) == {"x": 99}

    def test_publish_passes_extra_headers(self):
        asyncio.run(self.bus.connect())
        msg = Message(topic="t", payload={}, headers=MessageHeaders(extra={"x-tenant": "acme"}))
        asyncio.run(self.bus.publish(msg))
        headers_arg = self.mock_ap.Message.call_args.kwargs["headers"]
        assert headers_arg == {"x-tenant": "acme"}

    def test_publish_auto_connects_if_no_channel(self):
        assert self.bus._channel is None
        msg = Message(topic="t", payload={})
        asyncio.run(self.bus.publish(msg))
        self.mock_ap.connect_robust.assert_called_once()
        self.mock_ex.publish.assert_called_once()

    def test_publish_batch_sends_all(self):
        asyncio.run(self.bus.connect())
        msgs = [Message(topic="t", payload={"i": i}) for i in range(3)]
        asyncio.run(self.bus.publish_batch(msgs))
        assert self.mock_ex.publish.call_count == 3

    def test_publish_batch_empty_does_nothing(self):
        asyncio.run(self.bus.connect())
        asyncio.run(self.bus.publish_batch([]))
        self.mock_ex.publish.assert_not_called()

    def test_implements_message_bus_interface(self):
        from mp_commons.kernel.messaging import MessageBus
        assert issubclass(RabbitMQMessageBus, MessageBus)


# ===========================================================================
# §31.2 – Connection retry with RetryPolicy
# ===========================================================================

class TestRabbitMQRetryPolicy:
    def test_connect_with_retry_policy_retries_on_failure(self):
        mock_ap, mock_conn, mock_ch, _ = _make_mock_aio_pika()
        mock_conn.channel = AsyncMock(return_value=mock_ch)
        mock_ap.connect_robust.side_effect = [ConnectionError("refused"), mock_conn]

        policy = RetryPolicy(
            max_attempts=3,
            backoff=ConstantBackoff(delay=0.0),
            jitter=NoJitter(),
            retryable_exceptions=(ConnectionError,),
        )
        with patch("mp_commons.adapters.rabbitmq.bus._require_aio_pika", return_value=mock_ap):
            bus = RabbitMQMessageBus(retry_policy=policy)
            asyncio.run(bus.connect())
        assert mock_ap.connect_robust.call_count == 2
        assert bus._channel is mock_ch

    def test_connect_with_retry_raises_after_max_attempts(self):
        mock_ap, _, _, _ = _make_mock_aio_pika()
        mock_ap.connect_robust.side_effect = ConnectionError("refused")

        policy = RetryPolicy(
            max_attempts=2,
            backoff=ConstantBackoff(delay=0.0),
            jitter=NoJitter(),
            retryable_exceptions=(ConnectionError,),
        )
        with patch("mp_commons.adapters.rabbitmq.bus._require_aio_pika", return_value=mock_ap):
            bus = RabbitMQMessageBus(retry_policy=policy)
            with pytest.raises(ConnectionError, match="refused"):
                asyncio.run(bus.connect())

    def test_no_retry_policy_raises_immediately_on_failure(self):
        mock_ap, _, _, _ = _make_mock_aio_pika()
        mock_ap.connect_robust.side_effect = ConnectionError("refused")

        with patch("mp_commons.adapters.rabbitmq.bus._require_aio_pika", return_value=mock_ap):
            bus = RabbitMQMessageBus()
            with pytest.raises(ConnectionError):
                asyncio.run(bus.connect())
        mock_ap.connect_robust.assert_called_once()

    def test_stores_retry_policy_on_instance(self):
        mock_ap, _, _, _ = _make_mock_aio_pika()
        policy = RetryPolicy(max_attempts=5)
        with patch("mp_commons.adapters.rabbitmq.bus._require_aio_pika", return_value=mock_ap):
            bus = RabbitMQMessageBus(retry_policy=policy)
        assert bus._retry is policy
