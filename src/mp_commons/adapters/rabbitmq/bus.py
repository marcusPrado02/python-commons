"""RabbitMQ adapter – RabbitMQMessageBus."""
from __future__ import annotations

import json
from typing import Any

from mp_commons.kernel.messaging import Message, MessageBus


def _require_aio_pika() -> Any:
    try:
        import aio_pika  # type: ignore[import-untyped]
        return aio_pika
    except ImportError as exc:
        raise ImportError("Install 'mp-commons[rabbitmq]' (aio-pika) to use this adapter") from exc


class RabbitMQMessageBus(MessageBus):
    """RabbitMQ publisher implementing ``MessageBus`` via aio-pika."""

    def __init__(self, url: str = "amqp://guest:guest@localhost/") -> None:
        _require_aio_pika()
        self._url = url
        self._connection: Any = None
        self._channel: Any = None

    async def connect(self) -> None:
        aio_pika = _require_aio_pika()
        self._connection = await aio_pika.connect_robust(self._url)
        self._channel = await self._connection.channel()

    async def close(self) -> None:
        if self._connection:
            await self._connection.close()

    async def __aenter__(self) -> "RabbitMQMessageBus":
        await self.connect()
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    async def publish(self, message: Message[Any]) -> None:
        aio_pika = _require_aio_pika()
        if self._channel is None:
            await self.connect()
        body = json.dumps(message.payload, default=str).encode()
        await self._channel.default_exchange.publish(
            aio_pika.Message(body=body, headers=message.headers.extra or {}),
            routing_key=message.topic,
        )

    async def publish_batch(self, messages: list[Message[Any]]) -> None:
        for msg in messages:
            await self.publish(msg)


__all__ = ["RabbitMQMessageBus"]
