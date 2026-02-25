"""Application notifications – TwilioSmsSender (requires httpx)."""
from __future__ import annotations

from base64 import b64encode
from dataclasses import dataclass
from typing import Any

from mp_commons.application.notifications.sms import SmsMessage

__all__ = ["TwilioConfig", "TwilioSmsSender"]


def _require_httpx() -> Any:  # pragma: no cover
    try:
        import httpx  # noqa: PLC0415
        return httpx
    except ImportError as exc:
        raise ImportError(
            "httpx is required for Twilio SMS sender. "
            "Install it with: pip install httpx"
        ) from exc


@dataclass
class TwilioConfig:
    account_sid: str
    auth_token: str
    from_number: str  # E.164, e.g. +15550001234
    api_url: str = "https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
    timeout: float = 10.0
    max_retries: int = 3


class TwilioSmsSender:
    """SmsSender that sends via the Twilio REST API."""

    def __init__(self, config: TwilioConfig) -> None:
        self._config = config

    async def send(self, message: SmsMessage) -> str:  # pragma: no cover
        httpx = _require_httpx()
        url = self._config.api_url.format(account_sid=self._config.account_sid)
        creds = b64encode(
            f"{self._config.account_sid}:{self._config.auth_token}".encode()
        ).decode()
        headers = {"Authorization": f"Basic {creds}"}
        data = {
            "To": message.to,
            "From": message.sender_id or self._config.from_number,
            "Body": message.body,
        }
        for attempt in range(self._config.max_retries):
            async with httpx.AsyncClient(timeout=self._config.timeout) as client:
                resp = await client.post(url, data=data, headers=headers)
                if resp.status_code == 429:
                    import asyncio  # noqa: PLC0415
                    await asyncio.sleep(2 ** attempt)
                    continue
                resp.raise_for_status()
                return resp.json().get("sid", "")
        raise RuntimeError("Twilio: exceeded max retries (rate limited)")
