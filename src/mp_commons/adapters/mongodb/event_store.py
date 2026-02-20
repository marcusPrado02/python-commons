"""MongoDB adapter — MongoEventStore."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from mp_commons.application.event_sourcing.store import EventStore, OptimisticConcurrencyError
from mp_commons.application.event_sourcing.stored_event import StoredEvent


class MongoEventStore(EventStore):
    """Append-only event store backed by MongoDB.

    Stores events in the ``domain_events`` collection with a **unique
    compound index** on ``(stream_id, version)`` that acts as the
    optimistic-concurrency guard.

    Call :meth:`create_indexes` once on startup before the first
    :meth:`append` call.

    Optimistic locking strategy
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Before inserting, the current event count for *stream_id* is compared
    against *expected_version*.  If they differ,
    :class:`~mp_commons.application.event_sourcing.OptimisticConcurrencyError`
    is raised immediately.  Even without that pre-check, the unique index
    catches racing writes and re-raises the conflict as the same error.
    """

    COLLECTION_NAME = "domain_events"

    def __init__(self, collection: Any) -> None:
        self._col = collection

    # ------------------------------------------------------------------
    # Index management
    # ------------------------------------------------------------------

    @classmethod
    async def create_indexes(cls, collection: Any) -> None:
        """Create the unique ``(stream_id, version)`` index.

        Idempotent — safe to call repeatedly.
        """
        await collection.create_index(
            [("stream_id", 1), ("version", 1)],
            unique=True,
            name="idx_stream_version",
        )

    # ------------------------------------------------------------------
    # EventStore interface
    # ------------------------------------------------------------------

    async def append(
        self,
        stream_id: str,
        events: list[StoredEvent],
        expected_version: int,
    ) -> None:
        if not events:
            return

        current = await self._col.count_documents({"stream_id": stream_id})
        if current != expected_version:
            raise OptimisticConcurrencyError(stream_id, expected_version, current)

        docs = [self._to_doc(ev) for ev in events]
        try:
            await self._col.insert_many(docs, ordered=True)
        except Exception as exc:
            # DuplicateKeyError from a concurrent writer
            if "duplicate key" in str(exc).lower() or "E11000" in str(exc):
                actual = await self._col.count_documents({"stream_id": stream_id})
                raise OptimisticConcurrencyError(
                    stream_id, expected_version, actual
                ) from None
            raise

    async def load(
        self,
        stream_id: str,
        from_version: int = 0,
    ) -> list[StoredEvent]:
        cursor = self._col.find(
            {"stream_id": stream_id, "version": {"$gt": from_version}},
            sort=[("version", 1)],
        )
        return [self._from_doc(doc) async for doc in cursor]

    # ------------------------------------------------------------------
    # (De)serialisation helpers
    # ------------------------------------------------------------------

    def _to_doc(self, ev: StoredEvent) -> dict[str, Any]:
        return {
            # Compound natural key as _id keeps the collection de-duplication free
            "_id": f"{ev.stream_id}#{ev.version}",
            "stream_id": ev.stream_id,
            "version": ev.version,
            "event_type": ev.event_type,
            "payload": ev.payload,
            "metadata": ev.metadata,
            "occurred_at": ev.occurred_at,
        }

    def _from_doc(self, doc: dict[str, Any]) -> StoredEvent:
        return StoredEvent(
            stream_id=doc["stream_id"],
            version=doc["version"],
            event_type=doc["event_type"],
            payload=doc.get("payload", b""),
            metadata=doc.get("metadata", {}),
            occurred_at=doc.get("occurred_at", datetime.now(UTC)),
        )


__all__ = ["MongoEventStore"]
