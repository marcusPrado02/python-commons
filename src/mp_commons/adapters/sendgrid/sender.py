"""SendGrid email adapter — implements :class:`EmailSender` (A-05).

Sends email via the SendGrid Mail Send API v3 using ``httpx`` for async
HTTP so that no additional SDK dependency is required.

Usage::

    from mp_commons.adapters.sendgrid import SendGridEmailSender
    from mp_commons.application.email.message import EmailMessage

    sender = SendGridEmailSender(
        api_key="SG.xxxxxxxx",
        from_email="noreply@example.com",
        from_name="My App",
    )

    msg = EmailMessage(
        to=["user@example.com"],
        subject="Hello",
        html_body="<p>Hi there</p>",
    )
    message_id = await sender.send(msg)
"""

from __future__ import annotations

import logging
from typing import Any

from mp_commons.application.email.message import EmailMessage

logger = logging.getLogger(__name__)

_SENDGRID_API_URL = "https://api.sendgrid.com/v3/mail/send"


def _require_httpx() -> Any:
    try:
        import httpx  # type: ignore[import-untyped]

        return httpx
    except ImportError as exc:
        raise ImportError(
            "httpx is required for SendGridEmailSender. Install it with: pip install 'httpx>=0.27'"
        ) from exc


def _build_payload(message: EmailMessage, from_email: str, from_name: str | None) -> dict:
    from_field: dict = {"email": from_email}
    if from_name:
        from_field["name"] = from_name

    personalizations: dict = {
        "to": [{"email": addr} for addr in message.to],
    }
    if message.cc:
        personalizations["cc"] = [{"email": addr} for addr in message.cc]
    if message.bcc:
        personalizations["bcc"] = [{"email": addr} for addr in message.bcc]
    if message.subject:
        personalizations["subject"] = message.subject

    payload: dict = {
        "personalizations": [personalizations],
        "from": from_field,
        "subject": message.subject,
        "content": [{"type": "text/html", "value": message.html_body}],
    }
    if message.text_body:
        payload["content"].insert(0, {"type": "text/plain", "value": message.text_body})
    if message.reply_to:
        payload["reply_to"] = {"email": message.reply_to}
    if message.attachments:
        import base64

        payload["attachments"] = [
            {
                "filename": att.filename,
                "type": att.content_type,
                "content": base64.b64encode(att.data).decode("ascii"),
                "disposition": "attachment",
            }
            for att in message.attachments
        ]
    return payload


class SendGridEmailSender:
    """Async :class:`~mp_commons.application.email.sender.EmailSender` backed
    by the SendGrid Mail Send v3 API.

    Parameters
    ----------
    api_key:
        SendGrid API key (starts with ``SG.``).
    from_email:
        Default sender email address.
    from_name:
        Optional display name for the sender.
    api_url:
        Override the SendGrid API endpoint (useful for testing).
    timeout:
        HTTP request timeout in seconds (default: 30).
    """

    def __init__(
        self,
        api_key: str,
        from_email: str,
        from_name: str | None = None,
        api_url: str = _SENDGRID_API_URL,
        timeout: float = 30.0,
    ) -> None:
        self._api_key = api_key
        self._from_email = from_email
        self._from_name = from_name
        self._api_url = api_url
        self._timeout = timeout

    async def send(self, message: EmailMessage) -> str:
        """Send *message* via SendGrid.

        Returns
        -------
        str
            The ``X-Message-Id`` returned by SendGrid, or an empty string
            if the header is absent.

        Raises
        ------
        httpx.HTTPStatusError
            If SendGrid returns a non-2xx status code.
        """
        httpx = _require_httpx()
        payload = _build_payload(message, self._from_email, self._from_name)
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(self._api_url, json=payload, headers=headers)
            response.raise_for_status()
            message_id = response.headers.get("x-message-id", "")
            logger.info(
                "sendgrid.sent to=%s subject=%r message_id=%s",
                message.to,
                message.subject,
                message_id,
            )
            return message_id

    async def send_bulk(self, messages: list[EmailMessage]) -> list[str]:
        """Send multiple messages and return their message-ids in order."""
        results: list[str] = []
        for msg in messages:
            mid = await self.send(msg)
            results.append(mid)
        return results


__all__ = ["SendGridEmailSender"]
