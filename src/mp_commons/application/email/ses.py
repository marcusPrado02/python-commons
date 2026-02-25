"""Application email – SesEmailSender (requires 'aiobotocore' extra)."""
from __future__ import annotations

import uuid
from typing import Any

from mp_commons.application.email.message import EmailMessage

__all__ = ["SesConfig", "SesEmailSender"]


def _require_aiobotocore() -> Any:  # pragma: no cover
    try:
        import aiobotocore.session  # noqa: PLC0415
        return aiobotocore.session
    except ImportError as exc:
        raise ImportError(
            "aiobotocore is required for SES email sending. "
            "Install it with: pip install aiobotocore"
        ) from exc


from dataclasses import dataclass


@dataclass
class SesConfig:
    region_name: str = "us-east-1"
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    source_email: str = "noreply@example.com"


class SesEmailSender:
    """EmailSender that sends via AWS SES using ``aiobotocore``."""

    def __init__(self, config: SesConfig) -> None:
        self._config = config

    async def send(self, message: EmailMessage) -> str:  # pragma: no cover
        session_mod = _require_aiobotocore()
        session = session_mod.get_session()
        kwargs: dict[str, Any] = {}
        if self._config.aws_access_key_id:
            kwargs["aws_access_key_id"] = self._config.aws_access_key_id
            kwargs["aws_secret_access_key"] = self._config.aws_secret_access_key
        async with session.create_client("ses", region_name=self._config.region_name, **kwargs) as client:
            dest: dict[str, Any] = {"ToAddresses": message.to}
            if message.cc:
                dest["CcAddresses"] = message.cc
            if message.bcc:
                dest["BccAddresses"] = message.bcc
            body: dict[str, Any] = {
                "Html": {"Data": message.html_body, "Charset": "UTF-8"},
            }
            if message.text_body:
                body["Text"] = {"Data": message.text_body, "Charset": "UTF-8"}
            resp = await client.send_email(
                Source=self._config.source_email,
                Destination=dest,
                Message={
                    "Subject": {"Data": message.subject, "Charset": "UTF-8"},
                    "Body": body,
                },
            )
            return resp.get("MessageId", str(uuid.uuid4()))

    async def send_bulk(self, messages: list[EmailMessage]) -> list[str]:  # pragma: no cover
        return [await self.send(m) for m in messages]
