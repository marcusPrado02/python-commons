"""Kafka adapter – KafkaProducer."""
from __future__ import annotations

import logging
from typing import Any

from mp_commons.kernel.messaging import Message, MessageBus, MessageSerializer
from mp_commons.adapters.kafka.serializer import KafkaMessageSerializer

logger = logging.getLogger(__name__)


def _require_aiokafka() -> Any:
    try:
        import aiokafka  # type: ignore[import-untyped]
        return aiokafka
    except ImportError as exc:
        raise ImportError("Install 'mp-commons[kafka]' to use the Kafka adapter") from exc


class KafkaProducer(MessageBus):
    """aiokafka-backed producer implementing ``MessageBus``."""

    def __init__(
        self,
        bootstrap_servers: str,
        serializer: MessageSerializer[Any] | None = None,
        **producer_kwargs: Any,
    ) -> None:
        aiokafka = _require_aiokafka()
        self._producer = aiokafka.AIOKafkaProducer(bootstrap_servers=bootstrap_servers, **producer_kwargs)
        self._serializer = serializer or KafkaMessageSerializer()
        self._started = False

    async def start(self) -> None:
        await self._producer.start()
        self._started = True

    async def stop(self) -> None:
        await self._producer.stop()
        self._started = False

    async def __aenter__(self) -> "KafkaProducer":
        await self.start()
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.stop()

    async def publish(self, message: Message[Any]) -> None:
        if not self._started:
            await self.start()
        headers = [(k, v.encode()) for k, v in (message.headers.extra or {}).items()]
        if message.headers.correlation_id:
            headers.append(("correlation-id", message.headers.correlation_id.encode()))
        await self._producer.send(
            topic=message.topic,
            value=self._serializer.serialize(message.payload),
            headers=headers,
            key=message.id.encode(),
        )
        logger.debug("kafka.published topic=%s id=%s", message.topic, message.id)

    async def publish_batch(self, messages: list[Message[Any]]) -> None:
        for msg in messages:
            await self.publish(msg)


__all__ = ["KafkaProducer"]
