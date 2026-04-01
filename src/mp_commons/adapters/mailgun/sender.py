"""Mailgun email adapter — implements :class:`EmailSender` (A-06).

Sends email via the Mailgun Messages API using ``httpx`` for async HTTP.
Supports both the US (api.mailgun.net) and EU (api.eu.mailgun.net) regions.

Usage::

    from mp_commons.adapters.mailgun import MailgunEmailSender
    from mp_commons.application.email.message import EmailMessage

    sender = MailgunEmailSender(
        api_key="key-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        domain="mg.example.com",
        from_email="noreply@mg.example.com",
        region="us",  # or "eu"
    )

    msg = EmailMessage(
        to=["user@example.com"],
        subject="Hello from Mailgun",
        html_body="<p>Hi there</p>",
    )
    message_id = await sender.send(msg)
"""
from __future__ import annotations

import logging
from typing import Any

from mp_commons.application.email.message import EmailMessage

logger = logging.getLogger(__name__)

_BASE_URLS = {
    "us": "https://api.mailgun.net/v3",
    "eu": "https://api.eu.mailgun.net/v3",
}


def _require_httpx() -> Any:
    try:
        import httpx  # type: ignore[import-untyped]
        return httpx
    except ImportError as exc:
        raise ImportError(
            "httpx is required for MailgunEmailSender. "
            "Install it with: pip install 'httpx>=0.27'"
        ) from exc


class MailgunEmailSender:
    """Async :class:`~mp_commons.application.email.sender.EmailSender` backed
    by the Mailgun Messages API.

    Parameters
    ----------
    api_key:
        Mailgun private API key (starts with ``key-``).
    domain:
        Your Mailgun sending domain (e.g. ``mg.example.com``).
    from_email:
        Default sender address.
    from_name:
        Optional display name for the sender.
    region:
        ``"us"`` (default) or ``"eu"`` — selects the API base URL.
    base_url:
        Override the full base URL (useful for testing; takes precedence
        over *region*).
    timeout:
        HTTP request timeout in seconds (default: 30).
    """

    def __init__(
        self,
        api_key: str,
        domain: str,
        from_email: str,
        from_name: str | None = None,
        *,
        region: str = "us",
        base_url: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        if region not in _BASE_URLS and base_url is None:
            raise ValueError(f"region must be 'us' or 'eu', got {region!r}")
        self._api_key = api_key
        self._domain = domain
        self._from_email = from_email
        self._from_name = from_name
        self._timeout = timeout
        resolved_base = base_url or _BASE_URLS[region]
        self._endpoint = f"{resolved_base}/{domain}/messages"

    def _from_address(self) -> str:
        if self._from_name:
            return f"{self._from_name} <{self._from_email}>"
        return self._from_email

    async def send(self, message: EmailMessage) -> str:
        """Send *message* via Mailgun.

        Returns
        -------
        str
            Mailgun message-id from the JSON response ``id`` field, or
            empty string on success without an id.

        Raises
        ------
        httpx.HTTPStatusError
            If Mailgun returns a non-2xx status code.
        """
        httpx = _require_httpx()

        data: dict[str, Any] = {
            "from": self._from_address(),
            "to": ", ".join(message.to),
            "subject": message.subject,
            "html": message.html_body,
        }
        if message.text_body:
            data["text"] = message.text_body
        if message.cc:
            data["cc"] = ", ".join(message.cc)
        if message.bcc:
            data["bcc"] = ", ".join(message.bcc)
        if message.reply_to:
            data["h:Reply-To"] = message.reply_to

        files: list[tuple[str, Any]] | None = None
        if message.attachments:
            files = [
                ("attachment", (att.filename, att.data, att.content_type))
                for att in message.attachments
            ]

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            if files:
                response = await client.post(
                    self._endpoint,
                    auth=("api", self._api_key),
                    data=data,
                    files=files,
                )
            else:
                response = await client.post(
                    self._endpoint,
                    auth=("api", self._api_key),
                    data=data,
                )
            response.raise_for_status()
            body = response.json()
            message_id: str = body.get("id", "")
            logger.info(
                "mailgun.sent to=%s subject=%r message_id=%s",
                message.to,
                message.subject,
                message_id,
            )
            return message_id

    async def send_bulk(self, messages: list[EmailMessage]) -> list[str]:
        """Send multiple messages and return their ids in order."""
        results: list[str] = []
        for msg in messages:
            mid = await self.send(msg)
            results.append(mid)
        return results


__all__ = ["MailgunEmailSender"]
