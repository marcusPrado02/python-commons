"""OpenSearch adapter — drop-in replacement for ElasticsearchClient (A-10).

Uses ``opensearch-py`` (``AsyncOpenSearch``) which exposes the same query DSL
and CRUD operations as ``elasticsearch-py``.  All method signatures and
:class:`OpenSearchSearchQuery` builders are identical to their Elasticsearch
counterparts, making migration a one-line import swap.

Usage::

    from mp_commons.adapters.opensearch import OpenSearchClient, OpenSearchRepository

    client = OpenSearchClient("https://localhost:9200", index_prefix="myapp_")

    async with client:
        await client.index("doc-1", {"name": "Alice"}, index="users")
        doc = await client.get("doc-1", index="users")
"""

from __future__ import annotations

import dataclasses
from typing import Any, Generic, TypeVar


def _require_opensearch() -> Any:
    try:
        from opensearchpy import AsyncOpenSearch  # type: ignore[import-untyped]

        return AsyncOpenSearch
    except ImportError as exc:
        raise ImportError(
            "opensearch-py is required for OpenSearchClient. "
            "Install it with: pip install 'opensearch-py>=2.4'"
        ) from exc


T = TypeVar("T")


class OpenSearchSearchQuery:
    """Fluent Query-DSL builder identical in interface to
    :class:`~mp_commons.adapters.elasticsearch.ElasticsearchSearchQuery`.
    """

    def __init__(self) -> None:
        self._must: list[dict[str, Any]] = []
        self._should: list[dict[str, Any]] = []
        self._sort: list[dict[str, Any]] = []
        self._from: int = 0
        self._size: int = 10

    def must(self, field: str, value: Any) -> OpenSearchSearchQuery:
        self._must.append({"term": {field: value}})
        return self

    def should(self, field: str, value: Any) -> OpenSearchSearchQuery:
        self._should.append({"term": {field: value}})
        return self

    def range(self, field: str, *, gte: Any = None, lte: Any = None) -> OpenSearchSearchQuery:
        conditions: dict[str, Any] = {}
        if gte is not None:
            conditions["gte"] = gte
        if lte is not None:
            conditions["lte"] = lte
        self._must.append({"range": {field: conditions}})
        return self

    def sort(self, field: str, order: str = "asc") -> OpenSearchSearchQuery:
        self._sort.append({field: {"order": order}})
        return self

    def paginate(self, page: int, size: int) -> OpenSearchSearchQuery:
        self._from = (page - 1) * size
        self._size = size
        return self

    def build(self) -> dict[str, Any]:
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


class OpenSearchClient:
    """Thin async wrapper around ``AsyncOpenSearch``.

    Parameters
    ----------
    url:
        Full URL to the OpenSearch cluster (e.g. ``http://localhost:9200``).
    index_prefix:
        Optional prefix prepended to every index name.
    **kwargs:
        Passed verbatim to ``AsyncOpenSearch``.
    """

    def __init__(self, url: str, index_prefix: str = "", **kwargs: Any) -> None:
        AsyncOpenSearch = _require_opensearch()
        self._client = AsyncOpenSearch(url, **kwargs)
        self._prefix = index_prefix

    def _index(self, name: str) -> str:
        return f"{self._prefix}{name}" if self._prefix else name

    async def index(self, doc_id: str, body: dict[str, Any], *, index: str) -> None:
        """Index (create or replace) a document."""
        await self._client.index(index=self._index(index), id=doc_id, body=body)

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
        """Delete a document by ID.  No-op if not found."""
        try:
            await self._client.delete(index=self._index(index), id=doc_id)
        except Exception as exc:
            exc_str = str(exc)
            if (
                "NotFoundError" in type(exc).__name__
                or "404" in exc_str
                or "NotFoundError" in exc_str
            ):
                return
            raise

    async def search(self, query_dsl: dict[str, Any], *, index: str) -> list[dict[str, Any]]:
        """Execute a Query DSL search and return raw ``_source`` dicts."""
        resp = await self._client.search(index=self._index(index), body=query_dsl)
        return [hit["_source"] for hit in resp["hits"]["hits"]]

    async def close(self) -> None:
        await self._client.close()

    async def __aenter__(self) -> OpenSearchClient:
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()


class OpenSearchRepository(Generic[T]):
    """Domain-model-aware repository backed by :class:`OpenSearchClient`.

    Drop-in equivalent of :class:`~mp_commons.adapters.elasticsearch.ElasticsearchRepository`.
    """

    def __init__(self, client: OpenSearchClient, index: str, model: Any) -> None:
        self._client = client
        self._index = index
        self._model = model

    async def find_by_id(self, doc_id: str) -> T | None:
        raw = await self._client.get(doc_id, index=self._index)
        if raw is None:
            return None
        return self._model(**raw)  # type: ignore[return-value]

    async def save(self, doc: T) -> None:
        body = _to_dict(doc)
        doc_id = str(body.pop("id"))
        await self._client.index(doc_id, body, index=self._index)

    async def search(self, query_dsl: dict[str, Any]) -> list[T]:
        raw_list = await self._client.search(query_dsl, index=self._index)
        return [self._model(**raw) for raw in raw_list]

    async def delete(self, doc_id: str) -> None:
        await self._client.delete(doc_id, index=self._index)


def _to_dict(obj: Any) -> dict[str, Any]:
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return dataclasses.asdict(obj)  # type: ignore[arg-type]
    return dict(vars(obj))


__all__ = ["OpenSearchClient", "OpenSearchRepository", "OpenSearchSearchQuery"]
