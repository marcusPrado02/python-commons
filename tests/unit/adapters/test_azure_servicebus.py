"""Unit tests for AzureServiceBusProducer and AzureServiceBusConsumer (A-01)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import mp_commons.adapters.azure_servicebus.bus as _mod


def _stub_azure(monkeypatch) -> tuple[MagicMock, MagicMock]:
    """Stub azure.servicebus and azure.identity modules."""
    mock_sb_client = MagicMock()
    mock_sb_client.__aenter__ = AsyncMock(return_value=mock_sb_client)
    mock_sb_client.__aexit__ = AsyncMock(return_value=False)

    mock_sender = MagicMock()
    mock_sender.__aenter__ = AsyncMock(return_value=mock_sender)
    mock_sender.__aexit__ = AsyncMock(return_value=False)
    mock_sender.send_messages = AsyncMock()
    mock_sender.create_message_batch = AsyncMock(return_value=MagicMock())

    mock_sb_client.get_queue_sender.return_value = mock_sender

    mock_credential = MagicMock()
    mock_credential.return_value = MagicMock()

    monkeypatch.setattr(_mod, "_require_servicebus", lambda: MagicMock(return_value=mock_sb_client))
    monkeypatch.setattr(_mod, "_require_identity", lambda: mock_credential)

    return mock_sb_client, mock_sender


class TestAzureServiceBusProducer:
    @pytest.mark.asyncio
    async def test_send_serialises_payload_as_json(self, monkeypatch):
        from mp_commons.adapters.azure_servicebus.bus import AzureServiceBusProducer

        sent_msgs: list = []

        mock_sb_class = MagicMock()
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        mock_sender = MagicMock()
        mock_sender.__aenter__ = AsyncMock(return_value=mock_sender)
        mock_sender.__aexit__ = AsyncMock(return_value=False)

        async def capture(msg):
            sent_msgs.append(msg)

        mock_sender.send_messages = capture
        mock_client.get_queue_sender.return_value = mock_sender
        mock_sb_class.return_value = mock_client

        import sys
        import types

        # Stub azure.servicebus.aio and azure.servicebus
        aio_mod = types.ModuleType("azure.servicebus.aio")
        aio_mod.ServiceBusClient = mock_sb_class  # type: ignore[attr-defined]
        sb_mod = types.ModuleType("azure.servicebus")

        class _FakeMsg:
            def __init__(self, body):
                self.body = body

        sb_mod.ServiceBusMessage = _FakeMsg  # type: ignore[attr-defined]
        azure_mod = sys.modules.get("azure") or types.ModuleType("azure")
        azure_mod.servicebus = sb_mod  # type: ignore[attr-defined]

        with patch.dict(
            "sys.modules",
            {
                "azure.servicebus.aio": aio_mod,
                "azure.servicebus": sb_mod,
                "azure": azure_mod,
            },
        ):
            monkeypatch.setattr(_mod, "_require_servicebus", lambda: mock_sb_class)
            monkeypatch.setattr(_mod, "_require_identity", MagicMock)

            producer = AzureServiceBusProducer("ns.servicebus.net", "orders")
            producer._client = mock_client

            await producer.send({"event": "OrderCreated", "id": "o-1"})

        assert len(sent_msgs) == 1
        parsed = json.loads(sent_msgs[0].body)
        assert parsed["event"] == "OrderCreated"

    @pytest.mark.asyncio
    async def test_missing_azure_raises(self, monkeypatch):
        from mp_commons.adapters.azure_servicebus.bus import AzureServiceBusProducer

        monkeypatch.setattr(
            _mod, "_require_servicebus", lambda: (_ for _ in ()).throw(ImportError("no azure"))
        )

        producer = AzureServiceBusProducer("ns", "q")
        with pytest.raises((ImportError, StopAsyncIteration, Exception)):
            await producer.__aenter__()


class TestAzureServiceBusConsumer:
    @pytest.mark.asyncio
    async def test_receive_yields_decoded_payload(self, monkeypatch):
        from mp_commons.adapters.azure_servicebus.bus import AzureServiceBusConsumer

        payload = {"event": "OrderCreated"}
        encoded = json.dumps(payload).encode()

        mock_msg = MagicMock()
        mock_msg.body = iter([encoded])

        mock_receiver = MagicMock()
        mock_receiver.__aenter__ = AsyncMock(return_value=mock_receiver)
        mock_receiver.__aexit__ = AsyncMock(return_value=False)
        mock_receiver.complete_message = AsyncMock()
        mock_receiver.abandon_message = AsyncMock()

        async def _aiter(_self):
            yield mock_msg

        mock_receiver.__aiter__ = _aiter

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get_queue_receiver.return_value = mock_receiver

        consumer = AzureServiceBusConsumer("ns", "orders")
        consumer._client = mock_client

        received: list = []
        async for msg in consumer.receive():
            received.append(msg)

        assert len(received) == 1
        assert received[0]["event"] == "OrderCreated"
        mock_receiver.complete_message.assert_called_once_with(mock_msg)
