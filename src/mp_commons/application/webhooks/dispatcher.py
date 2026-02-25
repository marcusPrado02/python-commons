"""Application webhooks – WebhookDispatcher sends event payloads to endpoints."""
from __future__ import annotations

import json
import time
from typing import Any

from mp_commons.application.webhooks.endpoint import WebhookEndpoint
from mp_commons.application.webhooks.signature import WebhookSigner
from mp_commons.application.webhooks.store import WebhookDeliveryRecord, WebhookEndpointStore

__all__ = ["WebhookDispatcher"]


def _require_httpx() -> Any:  # pragma: no cover
    try:
        import httpx  # noqa: PLC0415
        return httpx
    except ImportError as exc:
        raise ImportError(
            "httpx is required for WebhookDispatcher. "
            "Install it with: pip install httpx"
        ) from exc


class WebhookDispatcher:
    """Finds matching endpoints and delivers signed event payloads via HTTP POST."""

    def __init__(
        self,
        store: WebhookEndpointStore,
        *,
        timeout: float = 10.0,
        max_retries: int = 3,
        retry_on: set[int] | None = None,
    ) -> None:
        self._store = store
        self._timeout = timeout
        self._max_retries = max_retries
        self._retry_on: set[int] = retry_on or {500, 502, 503, 504}
        self.delivery_log: list[WebhookDeliveryRecord] = []

    async def dispatch(self, event_type: str, payload: dict) -> list[WebhookDeliveryRecord]:
        """Dispatch *payload* for *event_type* to all matching endpoints."""
        endpoints = await self._store.find_by_event(event_type)
        records: list[WebhookDeliveryRecord] = []
        for endpoint in endpoints:
            record = await self._deliver(endpoint, event_type, payload)
            self.delivery_log.append(record)
            records.append(record)
        return records

    async def _deliver(
        self,
        endpoint: WebhookEndpoint,
        event_type: str,
        payload: dict,
    ) -> WebhookDeliveryRecord:  # pragma: no cover
        httpx = _require_httpx()
        body = json.dumps({"event": event_type, "data": payload}, separators=(",", ":")).encode("utf-8")
        signature = WebhookSigner.sign(body, endpoint.secret)
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Signature": signature,
            "X-Webhook-Event": event_type,
        }

        record = WebhookDeliveryRecord(endpoint_id=endpoint.id, event_type=event_type)
        last_error: str | None = None

        for attempt in range(1, self._max_retries + 1):
            record.attempts = attempt
            t0 = time.monotonic()
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    resp = await client.post(endpoint.url, content=body, headers=headers)
                record.duration_ms = (time.monotonic() - t0) * 1000
                record.http_status = resp.status_code
                if resp.status_code not in self._retry_on:
                    record.last_error = None
                    return record
                last_error = f"HTTP {resp.status_code}"
            except Exception as exc:  # noqa: BLE001
                record.duration_ms = (time.monotonic() - t0) * 1000
                last_error = str(exc)

        record.last_error = last_error
        return record
