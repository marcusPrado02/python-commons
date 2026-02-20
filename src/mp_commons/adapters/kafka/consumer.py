"""Kafka adapter – KafkaConsumer."""
from __future__ import annotations

from typing import Any

from mp_commons.kernel.messaging import MessageSerializer
from mp_commons.adapters.kafka.serializer import KafkaMessageSerializer


def _require_aiokafka() -> Any:
    try:
        import aiokafka  # type: ignore[import-untyped]
        return aiokafka
    except ImportError as exc:
        raise ImportError("Install 'mp-commons[kafka]' to use the Kafka adapter") from exc


class KafkaConsumer:
    """aiokafka-backed consumer."""

    def __init__(
        self,
        bootstrap_servers: str,
        group_id: str,
        topics: list[str],
        serializer: MessageSerializer[Any] | None = None,
        **kwargs: Any,
    ) -> None:
        aiokafka = _require_aiokafka()
        self._consumer = aiokafka.AIOKafkaConsumer(
            *topics,
            bootstrap_servers=bootstrap_servers,
            group_id=group_id,
            **kwargs,
        )
        self._serializer = serializer or KafkaMessageSerializer()

    async def start(self) -> None:
        await self._consumer.start()

    async def stop(self) -> None:
        await self._consumer.stop()

    async def __aiter__(self) -> Any:
        async for msg in self._consumer:
            yield msg

    async def __aenter__(self) -> "KafkaConsumer":
        await self.start()
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.stop()


__all__ = ["KafkaConsumer"]
