"""Unit tests for §63 Application — Email."""
from __future__ import annotations

import asyncio

import pytest
from mp_commons.application.email import (
    Attachment,
    EmailMessage,
    EmailSender,
    InMemoryEmailSender,
)


# ---------------------------------------------------------------------------
# EmailMessage
# ---------------------------------------------------------------------------
class TestEmailMessage:
    def test_basic_fields(self):
        msg = EmailMessage(
            to=["alice@example.com"],
            subject="Hello",
            html_body="<b>Hi</b>",
        )
        assert msg.to == ["alice@example.com"]
        assert msg.subject == "Hello"
        assert msg.html_body == "<b>Hi</b>"
        assert msg.text_body is None
        assert msg.cc == []
        assert msg.bcc == []
        assert msg.reply_to is None
        assert msg.attachments == []

    def test_all_recipients_combines_to_cc_bcc(self):
        msg = EmailMessage(
            to=["a@x.com"],
            subject="s",
            html_body="h",
            cc=["b@x.com"],
            bcc=["c@x.com"],
        )
        assert set(msg.all_recipients()) == {"a@x.com", "b@x.com", "c@x.com"}

    def test_all_recipients_no_cc_bcc(self):
        msg = EmailMessage(to=["a@x.com"], subject="s", html_body="h")
        assert msg.all_recipients() == ["a@x.com"]


class TestAttachment:
    def test_attachment_fields(self):
        att = Attachment(filename="report.pdf", content_type="application/pdf", data=b"%PDF")
        assert att.filename == "report.pdf"
        assert att.content_type == "application/pdf"
        assert att.data == b"%PDF"

    def test_attachment_frozen(self):
        att = Attachment(filename="f.txt", content_type="text/plain", data=b"x")
        with pytest.raises(Exception):  # frozen dataclass raises FrozenInstanceError
            att.filename = "other.txt"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# InMemoryEmailSender
# ---------------------------------------------------------------------------
class TestInMemoryEmailSender:
    def test_send_captures_message(self):
        async def _run():
            sender = InMemoryEmailSender()
            msg = EmailMessage(to=["x@y.com"], subject="Hi", html_body="<p>Hello</p>")
            msg_id = await sender.send(msg)
            assert sender.count == 1
            assert sender.last() is msg
            assert isinstance(msg_id, str)
            assert len(msg_id) > 0
        asyncio.run(_run())
    def test_send_bulk(self):
        async def _run():
            sender = InMemoryEmailSender()
            msgs = [
                EmailMessage(to=[f"user{i}@example.com"], subject=f"Sub {i}", html_body="body")
                for i in range(3)
            ]
            ids = await sender.send_bulk(msgs)
            assert sender.count == 3
            assert len(ids) == 3
            assert len(set(ids)) == 3  # all unique
        asyncio.run(_run())
    def test_reset_clears_outbox(self):
        async def _run():
            sender = InMemoryEmailSender()
            await sender.send(EmailMessage(to=["a@b.com"], subject="s", html_body="h"))
            sender.reset()
            assert sender.count == 0
            assert sender.last() is None
        asyncio.run(_run())
    def test_is_protocol_compatible(self):
        sender = InMemoryEmailSender()
        assert isinstance(sender, EmailSender)  # runtime_checkable

    def test_multiple_sends_accumulate(self):
        async def _run():
            sender = InMemoryEmailSender()
            for i in range(5):
                await sender.send(EmailMessage(to=[f"u{i}@x.com"], subject="s", html_body="h"))
            assert sender.count == 5
            assert sender.last().to == ["u4@x.com"]
        asyncio.run(_run())
