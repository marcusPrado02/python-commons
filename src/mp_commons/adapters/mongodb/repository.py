"""MongoDB adapter — MongoRepository generic base."""

from __future__ import annotations

from abc import abstractmethod
from typing import Any, Generic, TypeVar

from mp_commons.kernel.ddd import AggregateRoot, Repository
from mp_commons.kernel.ddd.specification import Specification
from mp_commons.kernel.errors import NotFoundError
from mp_commons.kernel.types.ids import EntityId

TAggregate = TypeVar("TAggregate", bound=AggregateRoot)


class MongoRepository(Repository[TAggregate], Generic[TAggregate]):
    """Generic MongoDB repository for aggregate roots.

    Subclasses must implement :meth:`_to_document` and
    :meth:`_from_document` to serialise the aggregate to/from a BSON-
    compatible ``dict``.  The document **must** contain an ``"_id"`` field
    equal to ``str(aggregate.id)``.

    Usage::

        class ProductRepository(MongoRepository[Product]):
            def _to_document(self, p: Product) -> dict:
                return {"_id": str(p.id), "name": p.name, "price": p.price}

            def _from_document(self, doc: dict) -> Product:
                return Product(EntityId(doc["_id"]), doc["name"], doc["price"])
    """

    def __init__(self, collection: Any) -> None:
        self._col = collection

    # ------------------------------------------------------------------
    # Abstract serialisation hooks
    # ------------------------------------------------------------------

    @abstractmethod
    def _to_document(self, agg: TAggregate) -> dict[str, Any]:
        """Return a BSON-compatible dict for *agg* (must include ``"_id"``)."""

    @abstractmethod
    def _from_document(self, doc: dict[str, Any]) -> TAggregate:
        """Reconstruct an aggregate from a MongoDB document."""

    # ------------------------------------------------------------------
    # Repository interface
    # ------------------------------------------------------------------

    async def get(self, id: EntityId) -> TAggregate | None:
        doc = await self._col.find_one({"_id": id.value})
        return self._from_document(doc) if doc is not None else None

    async def get_or_raise(self, id: EntityId) -> TAggregate:
        obj = await self.get(id)
        if obj is None:
            raise NotFoundError(type(self).__name__, id.value)
        return obj

    async def save(self, agg: TAggregate) -> None:
        """Upsert the aggregate document keyed by ``_id``."""
        doc = self._to_document(agg)
        await self._col.replace_one({"_id": doc["_id"]}, doc, upsert=True)

    async def delete(self, id: EntityId) -> None:
        await self._col.delete_one({"_id": id.value})

    async def find_all(self) -> list[TAggregate]:
        cursor = self._col.find({})
        return [self._from_document(doc) async for doc in cursor]

    async def find_by(
        self, spec: Specification[TAggregate]
    ) -> list[TAggregate]:
        """Filter aggregates by *spec*.

        If *spec* exposes a ``to_mongo_filter() -> dict`` method the filter
        is pushed down to MongoDB; otherwise all documents are loaded and
        filtered in Python.
        """
        if hasattr(spec, "to_mongo_filter"):
            filter_dict: dict[str, Any] = spec.to_mongo_filter()  # type: ignore[attr-defined]
            cursor = self._col.find(filter_dict)
            return [self._from_document(doc) async for doc in cursor]
        all_aggs = await self.find_all()
        return [agg for agg in all_aggs if spec.is_satisfied_by(agg)]


__all__ = ["MongoRepository"]
