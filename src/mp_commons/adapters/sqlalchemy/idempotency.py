"""SQLAlchemy adapter – SqlAlchemyIdempotencyStore."""
from __future__ import annotations

from typing import Any

from mp_commons.kernel.messaging import IdempotencyKey, IdempotencyRecord, IdempotencyStore


class SqlAlchemyIdempotencyStore(IdempotencyStore):
    """SQLAlchemy-backed idempotency store."""

    def __init__(self, session: Any, model: Any | None = None) -> None:
        self._session = session
        self._model = model

    async def get(self, key: IdempotencyKey) -> IdempotencyRecord | None:
        if self._model is None:
            return None
        return await self._session.get(self._model, str(key))

    async def save(self, key: IdempotencyKey, record: IdempotencyRecord) -> None:
        if self._model is None:
            raise RuntimeError("IdempotencyModel not configured")
        self._session.add(self._model(key=str(key), response=record.response, status=record.status))

    async def complete(self, key: IdempotencyKey, response: bytes) -> None:
        from sqlalchemy import update  # type: ignore[import-untyped]
        if self._model is None:
            raise RuntimeError("IdempotencyModel not configured")
        await self._session.execute(
            update(self._model).where(self._model.key == str(key)).values(response=response, status="COMPLETED")
        )


__all__ = ["SqlAlchemyIdempotencyStore"]
