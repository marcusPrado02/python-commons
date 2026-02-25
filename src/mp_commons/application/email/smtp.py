"""Application email – SmtpEmailSender (requires 'aiosmtplib' extra)."""
from __future__ import annotations

import email.mime.multipart
import email.mime.text
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

from mp_commons.application.email.message import EmailMessage

__all__ = ["SmtpConfig", "SmtpEmailSender"]


def _require_aiosmtplib() -> Any:  # pragma: no cover
    try:
        import aiosmtplib  # noqa: PLC0415
        return aiosmtplib
    except ImportError as exc:
        raise ImportError(
            "aiosmtplib is required for SMTP email sending. "
            "Install it with: pip install aiosmtplib"
        ) from exc


@dataclass
class SmtpConfig:
    hostname: str
    port: int = 587
    username: str | None = None
    password: str | None = None
    use_tls: bool = False
    start_tls: bool = True
    timeout: float = 30.0


class SmtpEmailSender:
    """EmailSender that sends via SMTP using ``aiosmtplib``."""

    def __init__(self, config: SmtpConfig) -> None:
        self._config = config
        self._client: Any | None = None

    async def connect(self) -> None:  # pragma: no cover
        aiosmtplib = _require_aiosmtplib()
        self._client = aiosmtplib.SMTP(
            hostname=self._config.hostname,
            port=self._config.port,
            use_tls=self._config.use_tls,
            timeout=self._config.timeout,
        )
        await self._client.connect()
        if self._config.start_tls:
            await self._client.starttls()
        if self._config.username and self._config.password:
            await self._client.login(self._config.username, self._config.password)

    async def close(self) -> None:  # pragma: no cover
        if self._client:
            await self._client.quit()
            self._client = None

    async def __aenter__(self) -> "SmtpEmailSender":  # pragma: no cover
        await self.connect()
        return self

    async def __aexit__(self, *_: Any) -> None:  # pragma: no cover
        await self.close()

    def _build_mime(self, message: EmailMessage) -> email.mime.multipart.MIMEMultipart:
        msg = email.mime.multipart.MIMEMultipart("alternative")
        msg["Subject"] = message.subject
        msg["From"] = self._config.username or "noreply@localhost"
        msg["To"] = ", ".join(message.to)
        if message.cc:
            msg["Cc"] = ", ".join(message.cc)
        if message.reply_to:
            msg["Reply-To"] = message.reply_to

        if message.text_body:
            msg.attach(email.mime.text.MIMEText(message.text_body, "plain", "utf-8"))
        msg.attach(email.mime.text.MIMEText(message.html_body, "html", "utf-8"))
        return msg

    async def send(self, message: EmailMessage) -> str:  # pragma: no cover
        if self._client is None:
            await self.connect()
        mime = self._build_mime(message)
        await self._client.send_message(mime)
        return str(uuid.uuid4())

    async def send_bulk(self, messages: list[EmailMessage]) -> list[str]:  # pragma: no cover
        return [await self.send(m) for m in messages]
