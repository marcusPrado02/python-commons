"""Kafka adapter – KafkaOutboxDispatcher."""
from __future__ import annotations

import logging
from typing import Any

from mp_commons.kernel.messaging import Message, MessageHeaders, OutboxDispatcher, OutboxRepository
from mp_commons.adapters.kafka.producer import KafkaProducer

logger = logging.getLogger(__name__)


class KafkaOutboxDispatcher(OutboxDispatcher):
    """Reads pending outbox records and publishes them via Kafka."""

    def __init__(self, bus: KafkaProducer, repo: OutboxRepository) -> None:
        self._bus = bus
        self._repo = repo

    async def dispatch_pending(self) -> int:
        records = await self._repo.get_pending()
        dispatched = 0
        for record in records:
            try:
                msg: Message[Any] = Message(
                    id=record.id,
                    topic=record.topic,
                    payload=record.payload,
                    headers=MessageHeaders(
                        correlation_id=record.headers.get("correlation-id"),
                        extra=record.headers,
                    ),
                )
                await self._bus.publish(msg)
                await self._repo.mark_dispatched(record.id)
                dispatched += 1
            except Exception as exc:
                logger.error("outbox.dispatch_failed id=%s exc=%r", record.id, exc)
                await self._repo.mark_failed(record.id, str(exc))
        return dispatched


__all__ = ["KafkaOutboxDispatcher"]
