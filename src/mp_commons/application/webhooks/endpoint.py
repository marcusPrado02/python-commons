"""Application webhooks – WebhookEndpoint value object."""
from __future__ import annotations

from dataclasses import dataclass, field


__all__ = ["WebhookEndpoint"]


@dataclass(frozen=True)
class WebhookEndpoint:
    """A configured webhook endpoint that receives event payloads."""

    url: str
    secret: str
    events: frozenset[str] = field(default_factory=frozenset)
    enabled: bool = True
    id: str = ""

    def matches(self, event_type: str) -> bool:
        """Return True if this endpoint subscribes to *event_type*."""
        if not self.enabled:
            return False
        return not self.events or event_type in self.events
