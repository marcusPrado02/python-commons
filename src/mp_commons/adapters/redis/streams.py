"""Redis Streams adapter — producer, consumer group, outbox dispatcher, and entry type."""
from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from typing import Any

from mp_commons.kernel.messaging.outbox import OutboxRepository, OutboxStatus


@dataclasses.dataclass
class RedisStreamEntry:
    """A single entry read from a Redis Stream."""

    id: str
    fields: dict[str, bytes]
    parsed_at: datetime = dataclasses.field(default_factory=lambda: datetime.now(timezone.utc))

    def field_str(self, key: str, default: str = "") -> str:
        """Decode a bytes field value to str."""
        val = self.fields.get(key)
        if val is None:
            # Redis may return bytes keys; fall back
            val = self.fields.get(key.encode("utf-8"))
        if val is None:
            return default
        return val.decode("utf-8", errors="replace") if isinstance(val, bytes) else str(val)


# ---------------------------------------------------------------------------
# Producer
# ---------------------------------------------------------------------------


class RedisStreamProducer:
    """Publish entries to a Redis Stream.

    Parameters
    ----------
    redis:
        An :class:`redis.asyncio.Redis` client instance.
    """

    def __init__(self, redis: Any) -> None:
        self._redis = redis

    async def publish(
        self,
        stream: str,
        fields: dict[str, Any],
        *,
        maxlen: int | None = None,
    ) -> str:
        """Publish *fields* to *stream* and return the entry ID.

        Parameters
        ----------
        maxlen:
            Optional maximum stream length.  When provided the stream is
            trimmed via ``MAXLEN ~  maxlen`` (approximate trimming).
        """
        kwargs: dict[str, Any] = {}
        if maxlen is not None:
            kwargs["maxlen"] = maxlen
            kwargs["approximate"] = True
        entry_id = await self._redis.xadd(stream, fields, **kwargs)
        return entry_id.decode("utf-8") if isinstance(entry_id, bytes) else str(entry_id)


# ---------------------------------------------------------------------------
# Consumer group
# ---------------------------------------------------------------------------


class RedisStreamConsumerGroup:
    """Read and acknowledge entries from a Redis Stream consumer group.

    Parameters
    ----------
    redis:
        An :class:`redis.asyncio.Redis` client instance.
    """

    def __init__(self, redis: Any) -> None:
        self._redis = redis

    async def create_group(
        self,
        stream: str,
        group: str,
        start_id: str = "$",
        *,
        mkstream: bool = True,
    ) -> None:
        """Create *group* on *stream*, starting from *start_id*.

        No-ops if the group already exists.
        """
        try:
            await self._redis.xgroup_create(stream, group, id=start_id, mkstream=mkstream)
        except Exception as exc:
            if "BUSYGROUP" in str(exc):
                return  # group already exists
            raise

    async def read(
        self,
        stream: str,
        group: str,
        consumer: str,
        count: int = 10,
        block_ms: int = 0,
    ) -> list[RedisStreamEntry]:
        """Read up to *count* new entries and return as :class:`RedisStreamEntry` objects.

        Parameters
        ----------
        block_ms:
            Milliseconds to block waiting for new entries.  0 means non-blocking.
        """
        results = await self._redis.xreadgroup(
            groupname=group,
            consumername=consumer,
            streams={stream: ">"},
            count=count,
            block=block_ms or None,
        )
        entries: list[RedisStreamEntry] = []
        if results:
            for _stream, messages in results:
                for msg_id, msg_fields in messages:
                    entry_id = msg_id.decode("utf-8") if isinstance(msg_id, bytes) else str(msg_id)
                    # Decode field keys to str
                    decoded_fields = {
                        (k.decode("utf-8") if isinstance(k, bytes) else k): v
                        for k, v in msg_fields.items()
                    }
                    entries.append(RedisStreamEntry(id=entry_id, fields=decoded_fields))
        return entries

    async def ack(self, stream: str, group: str, *ids: str) -> int:
        """Acknowledge one or more entry IDs, removing them from the PEL.

        Returns the number of successfully acknowledged entries.
        """
        return await self._redis.xack(stream, group, *ids)


# ---------------------------------------------------------------------------
# Outbox dispatcher
# ---------------------------------------------------------------------------


class RedisStreamOutboxDispatcher:
    """Read pending outbox records and publish them to Redis Streams.

    Parameters
    ----------
    producer:
        A configured :class:`RedisStreamProducer`.
    outbox_repo:
        The :class:`~mp_commons.kernel.messaging.outbox.OutboxRepository`.
    """

    def __init__(self, producer: RedisStreamProducer, outbox_repo: Any) -> None:
        self._producer = producer
        self._repo = outbox_repo

    async def dispatch_pending(self) -> int:
        """Fetch pending outbox records, publish to Redis Streams, mark dispatched.

        Returns the number of records successfully dispatched.
        """
        records = await self._repo.get_pending()
        dispatched = 0
        for record in records:
            try:
                fields: dict[str, Any] = {
                    "id": record.id,
                    "event_type": record.event_type,
                    "aggregate_id": record.aggregate_id,
                    "aggregate_type": record.aggregate_type,
                    "payload": record.payload,
                }
                fields.update(record.headers)
                await self._producer.publish(record.topic, fields)
                await self._repo.mark_dispatched(record.id)
                dispatched += 1
            except Exception:
                await self._repo.mark_failed(record.id, error="dispatch failed")
        return dispatched


__all__ = [
    "RedisStreamConsumerGroup",
    "RedisStreamEntry",
    "RedisStreamOutboxDispatcher",
    "RedisStreamProducer",
]
