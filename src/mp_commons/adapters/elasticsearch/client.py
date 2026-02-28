"""Elasticsearch adapter implementation.

Requires ``elasticsearch[async]>=8.0``.  Import guarded — raises ``ImportError``
with a clear message when the extra is absent.
"""
from __future__ import annotations

import dataclasses
from typing import Any, Generic, Protocol, TypeVar, runtime_checkable


def _require_elasticsearch() -> Any:
    try:
        from elasticsearch import AsyncElasticsearch  # type: ignore[import-untyped]

        return AsyncElasticsearch
    except ImportError as exc:
        raise ImportError(
            "elasticsearch[async] is required for ElasticsearchClient. "
            "Install it with: pip install 'elasticsearch[async]>=8.0'"
        ) from exc


T = TypeVar("T")


class ElasticsearchSearchQuery:
    """Fluent DSL query builder.

    Produces a plain :class:`dict` compatible with the Elasticsearch Query DSL.

    Example::

        query = (
            ElasticsearchSearchQuery()
            .must("status", "active")
            .range("age", gte=18, lte=65)
            .sort("name", "asc")
            .paginate(page=1, size=25)
        )
        results = await repo.search(query.build())
    """

    def __init__(self) -> None:
        self._must: list[dict[str, Any]] = []
        self._should: list[dict[str, Any]] = []
        self._sort: list[dict[str, Any]] = []
        self._from: int = 0
        self._size: int = 10

    # ------------------------------------------------------------------
    # Clauses
    # ------------------------------------------------------------------

    def must(self, field: str, value: Any) -> "ElasticsearchSearchQuery":
        """Add a *must* (AND) term clause."""
        self._must.append({"term": {field: value}})
        return self

    def should(self, field: str, value: Any) -> "ElasticsearchSearchQuery":
        """Add a *should* (OR) term clause."""
        self._should.append({"term": {field: value}})
        return self

    def range(
        self,
        field: str,
        *,
        gte: Any = None,
        lte: Any = None,
    ) -> "ElasticsearchSearchQuery":
        """Add a range clause."""
        conditions: dict[str, Any] = {}
        if gte is not None:
            conditions["gte"] = gte
        if lte is not None:
            conditions["lte"] = lte
        self._must.append({"range": {field: conditions}})
        return self

    def sort(self, field: str, order: str = "asc") -> "ElasticsearchSearchQuery":
        """Add a sort field."""
        self._sort.append({field: {"order": order}})
        return self

    def paginate(self, page: int, size: int) -> "ElasticsearchSearchQuery":
        """Set pagination (1-based page)."""
        self._from = (page - 1) * size
        self._size = size
        return self

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def build(self) -> dict[str, Any]:
        """Return the final Elasticsearch query dictionary."""
        bool_clause: dict[str, Any] = {}
        if self._must:
            bool_clause["must"] = self._must
        if self._should:
            bool_clause["should"] = self._should

        dsl: dict[str, Any] = {
            "query": {"bool": bool_clause} if bool_clause else {"match_all": {}},
            "from": self._from,
            "size": self._size,
        }
        if self._sort:
            dsl["sort"] = self._sort
        return dsl


class ElasticsearchClient:
    """Thin async wrapper around :class:`AsyncElasticsearch`.

    Parameters
    ----------
    url:
        Full URL to the Elasticsearch cluster (e.g. ``http://localhost:9200``).
    index_prefix:
        Optional prefix prepended to every index name.  Useful for multi-tenant
        setups or environment separation.
    **kwargs:
        Passed verbatim to :class:`AsyncElasticsearch`.
    """

    def __init__(self, url: str, index_prefix: str = "", **kwargs: Any) -> None:
        AsyncElasticsearch = _require_elasticsearch()
        self._client = AsyncElasticsearch(url, **kwargs)
        self._prefix = index_prefix

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _index(self, name: str) -> str:
        return f"{self._prefix}{name}" if self._prefix else name

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def index(self, doc_id: str, body: dict[str, Any], *, index: str) -> None:
        """Index (create or replace) a document."""
        await self._client.index(index=self._index(index), id=doc_id, document=body)

    async def get(self, doc_id: str, *, index: str) -> dict[str, Any] | None:
        """Retrieve a document by ID.  Returns *None* if not found."""
        try:
            resp = await self._client.get(index=self._index(index), id=doc_id)
            return dict(resp["_source"])
        except Exception as exc:
            if "NotFoundError" in type(exc).__name__ or "404" in str(exc):
                return None
            raise

    async def delete(self, doc_id: str, *, index: str) -> None:
        """Delete a document by ID."""
        await self._client.delete(index=self._index(index), id=doc_id, ignore_status=404)

    async def search(self, query_dsl: dict[str, Any], *, index: str) -> list[dict[str, Any]]:
        """Execute a Query DSL search and return raw ``_source`` dicts."""
        resp = await self._client.search(index=self._index(index), body=query_dsl)
        return [hit["_source"] for hit in resp["hits"]["hits"]]

    async def close(self) -> None:
        """Close the underlying HTTP transport."""
        await self._client.close()

    async def __aenter__(self) -> "ElasticsearchClient":
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()


class ElasticsearchRepository(Generic[T]):
    """Domain-model-aware repository backed by :class:`ElasticsearchClient`.

    Parameters
    ----------
    client:
        A configured :class:`ElasticsearchClient`.
    index:
        Index name (without prefix — the client applies that).
    model:
        A callable that accepts a ``dict`` and returns a *T* instance
        (e.g. a Pydantic model class or a dataclass constructor).
    """

    def __init__(
        self,
        client: ElasticsearchClient,
        index: str,
        model: Any,
    ) -> None:
        self._client = client
        self._index = index
        self._model = model

    async def find_by_id(self, doc_id: str) -> T | None:
        """Return a model instance or *None* if not found."""
        raw = await self._client.get(doc_id, index=self._index)
        if raw is None:
            return None
        return self._model(**raw)  # type: ignore[return-value]

    async def save(self, doc: T) -> None:
        """Persist a model instance.

        The model must expose an ``id`` attribute and a ``model_dump()`` method
        (Pydantic v2) or ``__dict__`` for plain dataclasses.
        """
        body = _to_dict(doc)
        doc_id = str(body.pop("id"))
        await self._client.index(doc_id, body, index=self._index)

    async def search(self, query_dsl: dict[str, Any]) -> list[T]:
        """Execute a DSL query and deserialise results to *T*."""
        raw_list = await self._client.search(query_dsl, index=self._index)
        return [self._model(**raw) for raw in raw_list]

    async def delete(self, doc_id: str) -> None:
        """Delete a document."""
        await self._client.delete(doc_id, index=self._index)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_dict(obj: Any) -> dict[str, Any]:
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return dataclasses.asdict(obj)  # type: ignore[arg-type]
    return dict(vars(obj))


__all__ = [
    "ElasticsearchClient",
    "ElasticsearchRepository",
    "ElasticsearchSearchQuery",
]
