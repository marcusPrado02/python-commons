"""Unit tests for SQSTaskBus (A-07)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mp_commons.adapters.sqs.task_bus import SQSTaskBus


def _make_bus(**kwargs) -> SQSTaskBus:
    return SQSTaskBus(
        queue_url="https://sqs.us-east-1.amazonaws.com/123/test-queue",
        region_name="us-east-1",
        **kwargs,
    )


def _make_fifo_bus(**kwargs) -> SQSTaskBus:
    return SQSTaskBus(
        queue_url="https://sqs.us-east-1.amazonaws.com/123/tasks.fifo",
        region_name="us-east-1",
        **kwargs,
    )


def _make_sqs_client(message_id: str = "msg-123") -> MagicMock:
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client.send_message = AsyncMock(return_value={"MessageId": message_id})
    return client


class TestSQSTaskBusStandard:
    @pytest.mark.asyncio
    async def test_dispatch_returns_message_id(self):
        bus = _make_bus()
        mock_client = _make_sqs_client("ret-id-1")

        import mp_commons.adapters.sqs.task_bus as mod

        with patch.object(mod, "_require_aiobotocore") as mock_aio:
            mock_session = MagicMock()
            mock_session.create_client.return_value = mock_client
            mock_aio.return_value.AioSession.return_value = mock_session

            result = await bus.dispatch("send_email", {"user_id": "u-1"})

        assert result == "ret-id-1"

    @pytest.mark.asyncio
    async def test_dispatch_sends_json_body(self):
        bus = _make_bus()
        mock_client = _make_sqs_client()
        sent_kwargs: list = []

        async def capture(**kwargs):
            sent_kwargs.append(kwargs)
            return {"MessageId": "mid"}

        mock_client.send_message = capture

        import mp_commons.adapters.sqs.task_bus as mod

        with patch.object(mod, "_require_aiobotocore") as mock_aio:
            mock_session = MagicMock()
            mock_session.create_client.return_value = mock_client
            mock_aio.return_value.AioSession.return_value = mock_session

            await bus.dispatch("my_task", {"key": "value"})

        body = json.loads(sent_kwargs[0]["MessageBody"])
        assert body["task"] == "my_task"
        assert body["payload"] == {"key": "value"}

    @pytest.mark.asyncio
    async def test_countdown_sets_delay_seconds(self):
        bus = _make_bus()
        mock_client = _make_sqs_client()
        sent_kwargs: list = []

        async def capture(**kwargs):
            sent_kwargs.append(kwargs)
            return {"MessageId": "mid"}

        mock_client.send_message = capture

        import mp_commons.adapters.sqs.task_bus as mod

        with patch.object(mod, "_require_aiobotocore") as mock_aio:
            mock_session = MagicMock()
            mock_session.create_client.return_value = mock_client
            mock_aio.return_value.AioSession.return_value = mock_session

            await bus.dispatch("t", {}, countdown=60)

        assert sent_kwargs[0]["DelaySeconds"] == 60

    @pytest.mark.asyncio
    async def test_countdown_capped_at_900(self):
        bus = _make_bus()
        mock_client = _make_sqs_client()
        sent_kwargs: list = []

        async def capture(**kwargs):
            sent_kwargs.append(kwargs)
            return {"MessageId": "mid"}

        mock_client.send_message = capture

        import mp_commons.adapters.sqs.task_bus as mod

        with patch.object(mod, "_require_aiobotocore") as mock_aio:
            mock_session = MagicMock()
            mock_session.create_client.return_value = mock_client
            mock_aio.return_value.AioSession.return_value = mock_session

            await bus.dispatch("t", {}, countdown=9999)

        assert sent_kwargs[0]["DelaySeconds"] == 900

    @pytest.mark.asyncio
    async def test_no_fifo_attrs_for_standard_queue(self):
        bus = _make_bus()
        mock_client = _make_sqs_client()
        sent_kwargs: list = []

        async def capture(**kwargs):
            sent_kwargs.append(kwargs)
            return {"MessageId": "mid"}

        mock_client.send_message = capture

        import mp_commons.adapters.sqs.task_bus as mod

        with patch.object(mod, "_require_aiobotocore") as mock_aio:
            mock_session = MagicMock()
            mock_session.create_client.return_value = mock_client
            mock_aio.return_value.AioSession.return_value = mock_session

            await bus.dispatch("t", {})

        assert "MessageGroupId" not in sent_kwargs[0]
        assert "MessageDeduplicationId" not in sent_kwargs[0]


class TestSQSTaskBusFIFO:
    @pytest.mark.asyncio
    async def test_detects_fifo_queue(self):
        bus = _make_fifo_bus()
        assert bus._is_fifo is True

    @pytest.mark.asyncio
    async def test_fifo_includes_message_group_id(self):
        bus = _make_fifo_bus(default_message_group_id="grp-1")
        sent_kwargs: list = []

        mock_client = _make_sqs_client()

        async def capture(**kwargs):
            sent_kwargs.append(kwargs)
            return {"MessageId": "mid"}

        mock_client.send_message = capture

        import mp_commons.adapters.sqs.task_bus as mod

        with patch.object(mod, "_require_aiobotocore") as mock_aio:
            mock_session = MagicMock()
            mock_session.create_client.return_value = mock_client
            mock_aio.return_value.AioSession.return_value = mock_session

            await bus.dispatch("t", {})

        assert sent_kwargs[0]["MessageGroupId"] == "grp-1"

    @pytest.mark.asyncio
    async def test_per_message_group_id_overrides_default(self):
        bus = _make_fifo_bus(default_message_group_id="default")
        sent_kwargs: list = []

        mock_client = _make_sqs_client()

        async def capture(**kwargs):
            sent_kwargs.append(kwargs)
            return {"MessageId": "mid"}

        mock_client.send_message = capture

        import mp_commons.adapters.sqs.task_bus as mod

        with patch.object(mod, "_require_aiobotocore") as mock_aio:
            mock_session = MagicMock()
            mock_session.create_client.return_value = mock_client
            mock_aio.return_value.AioSession.return_value = mock_session

            await bus.dispatch("t", {}, message_group_id="custom-grp")

        assert sent_kwargs[0]["MessageGroupId"] == "custom-grp"

    @pytest.mark.asyncio
    async def test_fifo_auto_deduplication_id_is_uuid(self):
        bus = _make_fifo_bus()
        sent_kwargs: list = []

        mock_client = _make_sqs_client()

        async def capture(**kwargs):
            sent_kwargs.append(kwargs)
            return {"MessageId": "mid"}

        mock_client.send_message = capture

        import mp_commons.adapters.sqs.task_bus as mod

        with patch.object(mod, "_require_aiobotocore") as mock_aio:
            mock_session = MagicMock()
            mock_session.create_client.return_value = mock_client
            mock_aio.return_value.AioSession.return_value = mock_session

            await bus.dispatch("t", {})

        import uuid

        dedup_id = sent_kwargs[0]["MessageDeduplicationId"]
        # Must be a valid UUID4
        parsed = uuid.UUID(dedup_id)
        assert parsed.version == 4

    @pytest.mark.asyncio
    async def test_explicit_deduplication_id_used(self):
        bus = _make_fifo_bus()
        sent_kwargs: list = []

        mock_client = _make_sqs_client()

        async def capture(**kwargs):
            sent_kwargs.append(kwargs)
            return {"MessageId": "mid"}

        mock_client.send_message = capture

        import mp_commons.adapters.sqs.task_bus as mod

        with patch.object(mod, "_require_aiobotocore") as mock_aio:
            mock_session = MagicMock()
            mock_session.create_client.return_value = mock_client
            mock_aio.return_value.AioSession.return_value = mock_session

            await bus.dispatch("t", {}, message_deduplication_id="my-dedup-id")

        assert sent_kwargs[0]["MessageDeduplicationId"] == "my-dedup-id"


class TestSQSMissingDependency:
    @pytest.mark.asyncio
    async def test_missing_aiobotocore_raises(self):
        bus = _make_bus()

        import mp_commons.adapters.sqs.task_bus as mod

        with patch.object(mod, "_require_aiobotocore", side_effect=ImportError("no aio")):
            with pytest.raises(ImportError, match="no aio"):
                await bus.dispatch("t", {})
