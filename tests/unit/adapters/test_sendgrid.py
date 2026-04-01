"""Unit tests for SendGridEmailSender (A-05)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mp_commons.application.email.message import Attachment, EmailMessage
from mp_commons.adapters.sendgrid.sender import SendGridEmailSender, _build_payload


class TestBuildPayload:
    def test_basic_payload(self):
        msg = EmailMessage(to=["a@b.com"], subject="Hi", html_body="<p>Hi</p>")
        payload = _build_payload(msg, "from@example.com", "Sender")
        assert payload["from"] == {"email": "from@example.com", "name": "Sender"}
        assert payload["subject"] == "Hi"
        assert any(c["type"] == "text/html" for c in payload["content"])

    def test_from_without_name(self):
        msg = EmailMessage(to=["a@b.com"], subject="S", html_body="H")
        payload = _build_payload(msg, "from@example.com", None)
        assert payload["from"] == {"email": "from@example.com"}

    def test_text_body_prepended(self):
        msg = EmailMessage(
            to=["a@b.com"], subject="S", html_body="H", text_body="plain"
        )
        payload = _build_payload(msg, "x@y.com", None)
        assert payload["content"][0]["type"] == "text/plain"
        assert payload["content"][1]["type"] == "text/html"

    def test_cc_and_bcc_included(self):
        msg = EmailMessage(
            to=["a@b.com"], subject="S", html_body="H",
            cc=["cc@b.com"], bcc=["bcc@b.com"],
        )
        payload = _build_payload(msg, "x@y.com", None)
        personalization = payload["personalizations"][0]
        assert {"email": "cc@b.com"} in personalization["cc"]
        assert {"email": "bcc@b.com"} in personalization["bcc"]

    def test_reply_to_included(self):
        msg = EmailMessage(
            to=["a@b.com"], subject="S", html_body="H", reply_to="rt@b.com"
        )
        payload = _build_payload(msg, "x@y.com", None)
        assert payload["reply_to"] == {"email": "rt@b.com"}

    def test_attachments_base64_encoded(self):
        att = Attachment(filename="test.txt", content_type="text/plain", data=b"hello")
        msg = EmailMessage(
            to=["a@b.com"], subject="S", html_body="H", attachments=[att]
        )
        payload = _build_payload(msg, "x@y.com", None)
        import base64
        assert payload["attachments"][0]["content"] == base64.b64encode(b"hello").decode()
        assert payload["attachments"][0]["filename"] == "test.txt"


class TestSendGridEmailSender:
    def _make_sender(self, **kwargs) -> SendGridEmailSender:
        return SendGridEmailSender(
            api_key="SG.test",
            from_email="sender@example.com",
            **kwargs,
        )

    def _mock_response(self, message_id: str = "test-id") -> MagicMock:
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.headers = {"x-message-id": message_id}
        return resp

    @pytest.mark.asyncio
    async def test_send_returns_message_id(self, respx_mock=None):
        sender = self._make_sender()
        msg = EmailMessage(to=["a@b.com"], subject="S", html_body="H")

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=self._mock_response("sg-msg-1"))

        import mp_commons.adapters.sendgrid.sender as mod
        with patch.object(mod, "_require_httpx") as mock_httpx:
            mock_httpx.return_value.AsyncClient.return_value = mock_client
            result = await sender.send(msg)

        assert result == "sg-msg-1"

    @pytest.mark.asyncio
    async def test_send_bulk_returns_list(self):
        sender = self._make_sender()
        messages = [
            EmailMessage(to=[f"u{i}@b.com"], subject="S", html_body="H")
            for i in range(3)
        ]

        call_count = 0

        async def fake_send(msg):
            nonlocal call_count
            call_count += 1
            return f"id-{call_count}"

        sender.send = fake_send  # type: ignore[method-assign]
        results = await sender.send_bulk(messages)
        assert results == ["id-1", "id-2", "id-3"]

    @pytest.mark.asyncio
    async def test_missing_httpx_raises_import_error(self):
        sender = self._make_sender()
        msg = EmailMessage(to=["a@b.com"], subject="S", html_body="H")

        import mp_commons.adapters.sendgrid.sender as mod
        with patch.object(mod, "_require_httpx", side_effect=ImportError("no httpx")):
            with pytest.raises(ImportError, match="no httpx"):
                await sender.send(msg)
