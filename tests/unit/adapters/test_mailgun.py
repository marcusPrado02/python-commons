"""Unit tests for MailgunEmailSender (A-06)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mp_commons.application.email.message import Attachment, EmailMessage
from mp_commons.adapters.mailgun.sender import MailgunEmailSender


def _make_sender(**kwargs) -> MailgunEmailSender:
    return MailgunEmailSender(
        api_key="key-test",
        domain="mg.example.com",
        from_email="sender@mg.example.com",
        **kwargs,
    )


def _mock_response(message_id: str = "<mg-123@mg.example.com>") -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"id": message_id, "message": "Queued. Thank you."}
    return resp


class TestMailgunEmailSender:
    def test_invalid_region_raises(self):
        with pytest.raises(ValueError, match="region"):
            MailgunEmailSender(
                api_key="key",
                domain="mg.example.com",
                from_email="x@y.com",
                region="invalid",
            )

    def test_eu_region_uses_eu_endpoint(self):
        sender = _make_sender(region="eu")
        assert "eu.mailgun.net" in sender._endpoint

    def test_base_url_override(self):
        sender = _make_sender(base_url="http://localhost:9000")
        assert sender._endpoint == "http://localhost:9000/mg.example.com/messages"

    def test_from_address_with_name(self):
        sender = _make_sender(from_name="My App")
        assert sender._from_address() == "My App <sender@mg.example.com>"

    def test_from_address_without_name(self):
        sender = _make_sender()
        assert sender._from_address() == "sender@mg.example.com"

    @pytest.mark.asyncio
    async def test_send_returns_message_id(self):
        sender = _make_sender()
        msg = EmailMessage(to=["a@b.com"], subject="Hi", html_body="<p>Hi</p>")

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=_mock_response("<mg-42>"))

        import mp_commons.adapters.mailgun.sender as mod
        with patch.object(mod, "_require_httpx") as mock_httpx:
            mock_httpx.return_value.AsyncClient.return_value = mock_client
            result = await sender.send(msg)

        assert result == "<mg-42>"

    @pytest.mark.asyncio
    async def test_send_with_text_body(self):
        sender = _make_sender()
        msg = EmailMessage(
            to=["a@b.com"], subject="S", html_body="H", text_body="plain"
        )
        posted_data: list = []

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        async def capture_post(*args, **kwargs):
            posted_data.append(kwargs.get("data", {}))
            return _mock_response()

        mock_client.post = capture_post

        import mp_commons.adapters.mailgun.sender as mod
        with patch.object(mod, "_require_httpx") as mock_httpx:
            mock_httpx.return_value.AsyncClient.return_value = mock_client
            await sender.send(msg)

        assert posted_data[0].get("text") == "plain"

    @pytest.mark.asyncio
    async def test_send_bulk_returns_list(self):
        sender = _make_sender()
        messages = [
            EmailMessage(to=[f"u{i}@b.com"], subject="S", html_body="H")
            for i in range(2)
        ]
        counter = 0

        async def fake_send(m):
            nonlocal counter
            counter += 1
            return f"id-{counter}"

        sender.send = fake_send  # type: ignore[method-assign]
        results = await sender.send_bulk(messages)
        assert results == ["id-1", "id-2"]

    @pytest.mark.asyncio
    async def test_missing_httpx_raises(self):
        sender = _make_sender()
        msg = EmailMessage(to=["a@b.com"], subject="S", html_body="H")

        import mp_commons.adapters.mailgun.sender as mod
        with patch.object(mod, "_require_httpx", side_effect=ImportError("no httpx")):
            with pytest.raises(ImportError):
                await sender.send(msg)

    @pytest.mark.asyncio
    async def test_attachments_sent_as_files(self):
        sender = _make_sender()
        att = Attachment(filename="f.txt", content_type="text/plain", data=b"data")
        msg = EmailMessage(
            to=["a@b.com"], subject="S", html_body="H", attachments=[att]
        )
        call_kwargs: list = []

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        async def capture(*args, **kwargs):
            call_kwargs.append(kwargs)
            return _mock_response()

        mock_client.post = capture

        import mp_commons.adapters.mailgun.sender as mod
        with patch.object(mod, "_require_httpx") as mock_httpx:
            mock_httpx.return_value.AsyncClient.return_value = mock_client
            await sender.send(msg)

        assert "files" in call_kwargs[0]
        assert call_kwargs[0]["files"][0][0] == "attachment"
