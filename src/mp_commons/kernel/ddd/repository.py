"""Repository port — generic async repository for aggregate roots."""

from __future__ import annotations

import abc
from typing import Generic, TypeVar

from mp_commons.kernel.ddd.aggregate import AggregateRoot
from mp_commons.kernel.types.ids import EntityId

TAggregate = TypeVar("TAggregate", bound=AggregateRoot)


class Repository(abc.ABC, Generic[TAggregate]):
    """Port: generic repository for aggregate roots.

    Concrete implementations live in ``adapters/sqlalchemy``,
    ``adapters/redis``, etc.
    """

    @abc.abstractmethod
    async def get(self, id: EntityId) -> TAggregate | None: ...

    @abc.abstractmethod
    async def get_or_raise(self, id: EntityId) -> TAggregate: ...

    @abc.abstractmethod
    async def save(self, aggregate: TAggregate) -> None: ...

    @abc.abstractmethod
    async def delete(self, id: EntityId) -> None: ...


__all__ = ["Repository"]
