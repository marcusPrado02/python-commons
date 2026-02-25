"""Unit tests for §64 Application — Push Notifications / SMS."""
from __future__ import annotations

import asyncio

import pytest
from mp_commons.application.notifications import (
    InMemoryPushSender,
    InMemorySmsSender,
    PushNotification,
    PushNotificationSender,
    SendResult,
    SmsMessage,
    SmsSender,
)


# ---------------------------------------------------------------------------
# PushNotification
# ---------------------------------------------------------------------------
class TestPushNotification:
    def test_default_fields(self):
        notif = PushNotification(
            device_tokens=["tok1"],
            title="New message",
            body="You have a new message",
        )
        assert notif.device_tokens == ["tok1"]
        assert notif.title == "New message"
        assert notif.badge is None
        assert notif.sound is None
        assert notif.data == {}

    def test_full_fields(self):
        notif = PushNotification(
            device_tokens=["tok1", "tok2"],
            title="Alert",
            body="Something happened",
            data={"key": "value"},
            badge=3,
            sound="default",
        )
        assert notif.badge == 3
        assert notif.sound == "default"
        assert notif.data["key"] == "value"


class TestSendResult:
    def test_success_result(self):
        r = SendResult(token="tok", success=True)
        assert r.success is True
        assert r.error is None

    def test_failure_result(self):
        r = SendResult(token="tok", success=False, error="Invalid token")
        assert r.success is False
        assert r.error == "Invalid token"

    def test_frozen(self):
        r = SendResult(token="t", success=True)
        with pytest.raises(Exception):
            r.success = False  # type: ignore[misc]


# ---------------------------------------------------------------------------
# InMemoryPushSender
# ---------------------------------------------------------------------------
class TestInMemoryPushSender:
    def test_send_captures_notification(self):
        async def _run():
            sender = InMemoryPushSender()
            notif = PushNotification(device_tokens=["t1", "t2"], title="Hi", body="Body")
            results = await sender.send(notif)
            assert sender.count == 1
            assert len(results) == 2
            assert all(r.success for r in results)
            assert {r.token for r in results} == {"t1", "t2"}
        asyncio.run(_run())
    def test_reset(self):
        async def _run():
            sender = InMemoryPushSender()
            notif = PushNotification(device_tokens=["t1"], title="Hi", body="Body")
            await sender.send(notif)
            sender.reset()
            assert sender.count == 0
        asyncio.run(_run())
    def test_is_protocol_compatible(self):
        sender = InMemoryPushSender()
        assert isinstance(sender, PushNotificationSender)

    def test_multiple_sends(self):
        async def _run():
            sender = InMemoryPushSender()
            for i in range(4):
                await sender.send(PushNotification(device_tokens=[f"tok{i}"], title="t", body="b"))
            assert sender.count == 4
        asyncio.run(_run())
# ---------------------------------------------------------------------------
# SmsMessage
# ---------------------------------------------------------------------------
class TestSmsMessage:
    def test_basic_fields(self):
        sms = SmsMessage(to="+15551234567", body="Hello!")
        assert sms.to == "+15551234567"
        assert sms.body == "Hello!"
        assert sms.sender_id is None

    def test_with_sender_id(self):
        sms = SmsMessage(to="+447911123456", body="Code: 1234", sender_id="MyApp")
        assert sms.sender_id == "MyApp"

    def test_frozen(self):
        sms = SmsMessage(to="+1", body="x")
        with pytest.raises(Exception):
            sms.to = "+2"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# InMemorySmsSender
# ---------------------------------------------------------------------------
class TestInMemorySmsSender:
    def test_send_captures_message(self):
        async def _run():
            sender = InMemorySmsSender()
            sms = SmsMessage(to="+15551234567", body="Test message")
            msg_id = await sender.send(sms)
            assert sender.count == 1
            assert sender.last() is sms
            assert msg_id == "mem-sms-1"
        asyncio.run(_run())
    def test_send_sequential_ids(self):
        async def _run():
            sender = InMemorySmsSender()
            id1 = await sender.send(SmsMessage(to="+1", body="a"))
            id2 = await sender.send(SmsMessage(to="+2", body="b"))
            assert id1 == "mem-sms-1"
            assert id2 == "mem-sms-2"
        asyncio.run(_run())
    def test_reset(self):
        async def _run():
            sender = InMemorySmsSender()
            await sender.send(SmsMessage(to="+1", body="x"))
            sender.reset()
            assert sender.count == 0
            assert sender.last() is None
        asyncio.run(_run())
    def test_is_protocol_compatible(self):
        sender = InMemorySmsSender()
        assert isinstance(sender, SmsSender)
