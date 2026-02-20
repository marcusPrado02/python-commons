"""NATS adapter – NatsMessageBus."""
from __future__ import annotations

import json
from typing import Any

from mp_commons.kernel.messaging import Message, MessageBus


def _require_nats() -> Any:
    try:
        import nats  # type: ignore[import-untyped]
        return nats
    except ImportError as exc:
        raise ImportError("Install 'mp-commons[nats]' to use the NATS adapter") from exc


class NatsMessageBus(MessageBus):
    """NATS JetStream publisher implementing ``MessageBus``."""

    def __init__(self, servers: str | list[str] = "nats://localhost:4222") -> None:
        _require_nats()
        self._servers = servers
        self._nc: Any = None
        self._js: Any = None

    async def connect(self) -> None:
        nats = _require_nats()
        self._nc = await nats.connect(self._servers)
        self._js = self._nc.jetstream()

    async def close(self) -> None:
        if self._nc:
            await self._nc.close()

    async def __aenter__(self) -> "NatsMessageBus":
        await self.connect()
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    async def publish(self, message: Message[Any]) -> None:
        if self._js is None:
            await self.connect()
        payload = json.dumps(message.payload, default=str).encode()
        await self._js.publish(message.topic, payload)

    async def publish_batch(self, messages: list[Message[Any]]) -> None:
        for msg in messages:
            await self.publish(msg)


__all__ = ["NatsMessageBus"]
