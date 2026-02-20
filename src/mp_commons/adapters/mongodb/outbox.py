"""MongoDB adapter — MongoOutboxStore."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from mp_commons.kernel.messaging import OutboxRecord, OutboxRepository, OutboxStatus


class MongoOutboxStore(OutboxRepository):
    """MongoDB-backed transactional outbox repository.

    Stores outbox records in the ``outbox_messages`` collection.  Call
    :meth:`create_indexes` once on startup to create:

    - a **TTL index** on ``dispatched_at`` (expires records after 7 days)
    - a **partial index** on ``status`` covering only ``PENDING`` documents
      for efficient relay queries.
    """

    COLLECTION_NAME = "outbox_messages"

    def __init__(self, collection: Any) -> None:
        self._col = collection

    # ------------------------------------------------------------------
    # Index management
    # ------------------------------------------------------------------

    @classmethod
    async def create_indexes(cls, collection: Any) -> None:
        """Create recommended indexes.  Idempotent — safe to call repeatedly."""
        # TTL index: automatically remove dispatched records after 7 days
        await collection.create_index(
            "dispatched_at",
            expireAfterSeconds=7 * 24 * 3600,
            sparse=True,
            name="idx_outbox_ttl",
        )
        # Partial index: only index PENDING status rows (relay query path)
        await collection.create_index(
            "status",
            partialFilterExpression={"status": OutboxStatus.PENDING.value},
            name="idx_outbox_pending",
        )

    # ------------------------------------------------------------------
    # OutboxRepository interface
    # ------------------------------------------------------------------

    async def save(self, record: OutboxRecord) -> None:
        await self._col.insert_one(self._to_doc(record))

    async def get_pending(self, limit: int = 100) -> list[OutboxRecord]:
        cursor = self._col.find({"status": OutboxStatus.PENDING.value}).limit(limit)
        return [self._from_doc(doc) async for doc in cursor]

    async def mark_dispatched(self, record_id: str) -> None:
        await self._col.update_one(
            {"_id": record_id},
            {
                "$set": {
                    "status": OutboxStatus.DISPATCHED.value,
                    "dispatched_at": datetime.now(UTC),
                }
            },
        )

    async def mark_failed(self, record_id: str, error: str) -> None:
        await self._col.update_one(
            {"_id": record_id},
            {
                "$set": {
                    "status": OutboxStatus.FAILED.value,
                    "last_error": error,
                    "retry_count": 1,
                }
            },
        )

    # ------------------------------------------------------------------
    # (De)serialisation helpers
    # ------------------------------------------------------------------

    def _to_doc(self, record: OutboxRecord) -> dict[str, Any]:
        return {
            "_id": record.id,
            "aggregate_id": record.aggregate_id,
            "aggregate_type": record.aggregate_type,
            "event_type": record.event_type,
            "topic": record.topic,
            "payload": record.payload,
            "headers": record.headers,
            "status": record.status.value,
            "created_at": record.created_at,
            "dispatched_at": record.dispatched_at,
            "retry_count": record.retry_count,
            "last_error": record.last_error,
        }

    def _from_doc(self, doc: dict[str, Any]) -> OutboxRecord:
        return OutboxRecord(
            id=doc["_id"],
            aggregate_id=doc.get("aggregate_id", ""),
            aggregate_type=doc.get("aggregate_type", ""),
            event_type=doc.get("event_type", ""),
            topic=doc.get("topic", ""),
            payload=doc.get("payload", b""),
            headers=doc.get("headers", {}),
            status=OutboxStatus(doc.get("status", OutboxStatus.PENDING.value)),
            created_at=doc.get("created_at", datetime.now(UTC)),
            dispatched_at=doc.get("dispatched_at"),
            retry_count=doc.get("retry_count", 0),
            last_error=doc.get("last_error"),
        )


__all__ = ["MongoOutboxStore"]
