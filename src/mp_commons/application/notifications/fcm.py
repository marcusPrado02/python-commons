"""Application notifications – FCMPushSender (requires httpx)."""
from __future__ import annotations

import json
from typing import Any

from mp_commons.application.notifications.push import PushNotification, SendResult

__all__ = ["FCMConfig", "FCMPushSender"]


def _require_httpx() -> Any:  # pragma: no cover
    try:
        import httpx  # noqa: PLC0415
        return httpx
    except ImportError as exc:
        raise ImportError(
            "httpx is required for FCM push sender. "
            "Install it with: pip install httpx"
        ) from exc


from dataclasses import dataclass


@dataclass
class FCMConfig:
    server_key: str
    api_url: str = "https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
    project_id: str = ""
    timeout: float = 10.0


class FCMPushSender:
    """PushNotificationSender that sends via Firebase Cloud Messaging HTTP v1."""

    def __init__(self, config: FCMConfig) -> None:
        self._config = config

    def _build_payload(self, notification: PushNotification, token: str) -> dict[str, Any]:
        msg: dict[str, Any] = {
            "token": token,
            "notification": {"title": notification.title, "body": notification.body},
        }
        if notification.data:
            msg["data"] = {k: str(v) for k, v in notification.data.items()}
        if notification.badge is not None:
            msg.setdefault("apns", {}).setdefault("payload", {}).setdefault("aps", {})["badge"] = notification.badge
        if notification.sound:
            msg.setdefault("android", {})["notification"] = {"sound": notification.sound}
        return {"message": msg}

    async def send(self, notification: PushNotification) -> list[SendResult]:  # pragma: no cover
        httpx = _require_httpx()
        results: list[SendResult] = []
        headers = {
            "Authorization": f"key={self._config.server_key}",
            "Content-Type": "application/json",
        }
        url = self._config.api_url.format(project_id=self._config.project_id)
        async with httpx.AsyncClient(timeout=self._config.timeout) as client:
            for token in notification.device_tokens:
                payload = self._build_payload(notification, token)
                try:
                    resp = await client.post(url, headers=headers, json=payload)
                    if resp.status_code in (200, 204):
                        results.append(SendResult(token=token, success=True))
                    else:
                        body = resp.json() if resp.content else {}
                        error = body.get("error", {}).get("message", resp.text)
                        results.append(SendResult(token=token, success=False, error=error))
                except Exception as exc:  # noqa: BLE001
                    results.append(SendResult(token=token, success=False, error=str(exc)))
        return results
