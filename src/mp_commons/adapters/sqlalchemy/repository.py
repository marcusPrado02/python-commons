"""SQLAlchemy adapter – SqlAlchemyRepositoryBase."""
from __future__ import annotations

from typing import Any, Generic, TypeVar

from mp_commons.kernel.ddd import AggregateRoot, Repository
from mp_commons.kernel.ddd.specification import Specification
from mp_commons.kernel.errors import NotFoundError
from mp_commons.kernel.types import EntityId

TAggregate = TypeVar("TAggregate", bound=AggregateRoot)


class SqlAlchemyRepositoryBase(Repository[TAggregate], Generic[TAggregate]):
    """Generic SQLAlchemy repository for aggregate roots."""

    def __init__(self, session: Any, model_class: type[TAggregate]) -> None:
        self._session = session
        self._model = model_class

    async def get(self, id: EntityId) -> TAggregate | None:
        return await self._session.get(self._model, id.value)

    async def get_or_raise(self, id: EntityId) -> TAggregate:
        obj = await self.get(id)
        if obj is None:
            raise NotFoundError(self._model.__name__, id.value)
        return obj

    async def save(self, aggregate: TAggregate) -> None:
        self._session.add(aggregate)

    async def delete(self, id: EntityId) -> None:
        obj = await self.get_or_raise(id)
        await self._session.delete(obj)

    async def find_all(self) -> list[TAggregate]:
        from sqlalchemy import select  # type: ignore[import-untyped]

        result = await self._session.execute(select(self._model))
        return list(result.scalars().all())

    async def find_by(self, spec: Specification[TAggregate]) -> list[TAggregate]:
        all_items = await self.find_all()
        return [item for item in all_items if spec.is_satisfied_by(item)]


__all__ = ["SqlAlchemyRepositoryBase"]
