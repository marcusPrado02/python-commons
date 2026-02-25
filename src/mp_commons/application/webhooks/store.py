"""Application webhooks – WebhookEndpointStore protocol + InMemory impl."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from mp_commons.application.webhooks.endpoint import WebhookEndpoint

__all__ = [
    "InMemoryWebhookEndpointStore",
    "WebhookDeliveryRecord",
    "WebhookEndpointStore",
]


@dataclass
class WebhookDeliveryRecord:
    """Audit record of a single webhook delivery attempt."""

    endpoint_id: str
    event_type: str
    http_status: int | None = None
    duration_ms: float = 0.0
    attempts: int = 0
    last_error: str | None = None


@runtime_checkable
class WebhookEndpointStore(Protocol):
    """Port: retrieve webhook endpoints registered for an event type."""

    async def find_by_event(self, event_type: str) -> list[WebhookEndpoint]: ...
    async def save(self, endpoint: WebhookEndpoint) -> None: ...
    async def remove(self, endpoint_id: str) -> None: ...


class InMemoryWebhookEndpointStore:
    """Fake WebhookEndpointStore for unit tests."""

    def __init__(self) -> None:
        self._endpoints: dict[str, WebhookEndpoint] = {}

    async def find_by_event(self, event_type: str) -> list[WebhookEndpoint]:
        return [ep for ep in self._endpoints.values() if ep.matches(event_type)]

    async def save(self, endpoint: WebhookEndpoint) -> None:
        self._endpoints[endpoint.id] = endpoint

    async def remove(self, endpoint_id: str) -> None:
        self._endpoints.pop(endpoint_id, None)

    def all(self) -> list[WebhookEndpoint]:
        return list(self._endpoints.values())
