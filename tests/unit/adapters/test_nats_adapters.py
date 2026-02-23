"""Unit tests for NATS adapter – §30.1–30.2 (mocked, no nats-py required)."""
from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mp_commons.adapters.nats.bus import NatsMessageBus
from mp_commons.kernel.messaging import Message


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_nats():
    """Return (mock_module, mock_nc, mock_js)."""
    mock_js = MagicMock()
    mock_js.publish = AsyncMock()

    mock_nc = MagicMock()
    mock_nc.jetstream.return_value = mock_js
    mock_nc.close = AsyncMock()

    mock_nats = MagicMock()
    mock_nats.connect = AsyncMock(return_value=mock_nc)
    return mock_nats, mock_nc, mock_js


# ===========================================================================
# Import guard
# ===========================================================================

class TestNatsImportError:
    def test_raises_import_error_without_lib(self):
        with patch(
            "mp_commons.adapters.nats.bus._require_nats",
            side_effect=ImportError("mp-commons[nats]"),
        ):
            with pytest.raises(ImportError, match="nats"):
                NatsMessageBus()


# ===========================================================================
# §30.1 – NatsMessageBus core
# ===========================================================================

class TestNatsMessageBusConnect:
    """Patch _require_nats for the full test so connect() can use the mock."""

    def setup_method(self):
        self.mock_nats, self.mock_nc, self.mock_js = _make_mock_nats()
        self._patcher = patch(
            "mp_commons.adapters.nats.bus._require_nats",
            return_value=self.mock_nats,
        )
        self._patcher.start()
        self.bus = NatsMessageBus()

    def teardown_method(self):
        self._patcher.stop()

    def test_connect_calls_nats_connect(self):
        asyncio.run(self.bus.connect())
        self.mock_nats.connect.assert_called_once_with("nats://localhost:4222")

    def test_connect_stores_jetstream(self):
        asyncio.run(self.bus.connect())
        self.mock_nc.jetstream.assert_called_once()
        assert self.bus._js is self.mock_js

    def test_connect_stores_nc(self):
        asyncio.run(self.bus.connect())
        assert self.bus._nc is self.mock_nc

    def test_close_calls_nc_close(self):
        asyncio.run(self.bus.connect())
        asyncio.run(self.bus.close())
        self.mock_nc.close.assert_called_once()

    def test_close_without_connect_is_noop(self):
        asyncio.run(self.bus.close())  # _nc is None
        self.mock_nc.close.assert_not_called()

    def test_context_manager_connects_and_closes(self):
        async def run():
            async with self.bus:
                pass

        asyncio.run(run())
        self.mock_nc.jetstream.assert_called_once()
        self.mock_nc.close.assert_called_once()


class TestNatsMessageBusCustomServers:
    def test_connect_with_custom_server_string(self):
        mock_nats, _, _ = _make_mock_nats()
        with patch("mp_commons.adapters.nats.bus._require_nats", return_value=mock_nats):
            bus = NatsMessageBus(servers="nats://broker:4222")
            asyncio.run(bus.connect())
        mock_nats.connect.assert_called_with("nats://broker:4222")

    def test_connect_with_server_list(self):
        mock_nats, _, _ = _make_mock_nats()
        servers = ["nats://n1:4222", "nats://n2:4222"]
        with patch("mp_commons.adapters.nats.bus._require_nats", return_value=mock_nats):
            bus = NatsMessageBus(servers=servers)
            asyncio.run(bus.connect())
        mock_nats.connect.assert_called_with(servers)


# ===========================================================================
# §30.2 – JetStream publish (at-least-once via ack)
# ===========================================================================

class TestNatsMessageBusPublish:
    """Patch _require_nats for the full test so publish() can use the mock."""

    def setup_method(self):
        self.mock_nats, self.mock_nc, self.mock_js = _make_mock_nats()
        self._patcher = patch(
            "mp_commons.adapters.nats.bus._require_nats",
            return_value=self.mock_nats,
        )
        self._patcher.start()
        self.bus = NatsMessageBus()

    def teardown_method(self):
        self._patcher.stop()

    def test_publish_calls_js_publish_with_subject(self):
        asyncio.run(self.bus.connect())
        msg = Message(topic="orders.created", payload={"id": 1})
        asyncio.run(self.bus.publish(msg))
        self.mock_js.publish.assert_called_once()
        assert self.mock_js.publish.call_args.args[0] == "orders.created"

    def test_publish_serializes_payload_as_json(self):
        asyncio.run(self.bus.connect())
        msg = Message(topic="t", payload={"x": 42})
        asyncio.run(self.bus.publish(msg))
        sent_bytes = self.mock_js.publish.call_args.args[1]
        assert json.loads(sent_bytes) == {"x": 42}

    def test_publish_auto_connects_if_not_connected(self):
        assert self.bus._js is None
        msg = Message(topic="t", payload={})
        asyncio.run(self.bus.publish(msg))
        self.mock_nc.jetstream.assert_called_once()
        self.mock_js.publish.assert_called_once()

    def test_publish_batch_publishes_all(self):
        asyncio.run(self.bus.connect())
        msgs = [Message(topic="t", payload={"i": i}) for i in range(4)]
        asyncio.run(self.bus.publish_batch(msgs))
        assert self.mock_js.publish.call_count == 4

    def test_publish_batch_empty_does_nothing(self):
        asyncio.run(self.bus.connect())
        asyncio.run(self.bus.publish_batch([]))
        self.mock_js.publish.assert_not_called()

    def test_publish_serializes_nested_object(self):
        asyncio.run(self.bus.connect())
        msg = Message(topic="t", payload={"user": {"name": "Alice"}})
        asyncio.run(self.bus.publish(msg))
        sent = json.loads(self.mock_js.publish.call_args.args[1])
        assert sent["user"]["name"] == "Alice"

    def test_implements_message_bus_interface(self):
        from mp_commons.kernel.messaging import MessageBus
        assert issubclass(NatsMessageBus, MessageBus)
