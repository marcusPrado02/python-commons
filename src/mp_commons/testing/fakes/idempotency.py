"""Testing fakes – InMemoryIdempotencyStore."""
from __future__ import annotations

from mp_commons.kernel.messaging import IdempotencyKey, IdempotencyRecord, IdempotencyStore


class InMemoryIdempotencyStore(IdempotencyStore):
    """Dict-backed idempotency store for tests."""

    def __init__(self) -> None:
        self._records: dict[str, IdempotencyRecord] = {}

    async def get(self, key: IdempotencyKey) -> IdempotencyRecord | None:
        return self._records.get(str(key))

    async def save(self, key: IdempotencyKey, record: IdempotencyRecord) -> None:
        self._records[str(key)] = record

    async def complete(self, key: IdempotencyKey, response: bytes) -> None:
        record = self._records.get(str(key))
        if record is not None:
            self._records[str(key)] = IdempotencyRecord(
                key=record.key,
                response=response,
                status="COMPLETED",
            )

    def all_keys(self) -> list[str]:
        return list(self._records.keys())


__all__ = ["InMemoryIdempotencyStore"]
