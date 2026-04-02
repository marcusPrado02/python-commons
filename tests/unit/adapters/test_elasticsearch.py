"""Unit tests for the Elasticsearch adapter (§48)."""

from __future__ import annotations

import sys
import types
from unittest.mock import AsyncMock, MagicMock

# ---------------------------------------------------------------------------
# Stub the elasticsearch package so tests run without the real library
# ---------------------------------------------------------------------------

_es_module = types.ModuleType("elasticsearch")


class _FakeNotFoundError(Exception):
    pass


_es_module.NotFoundError = _FakeNotFoundError  # type: ignore[attr-defined]

_async_es_class = MagicMock(name="AsyncElasticsearch")
_es_module.AsyncElasticsearch = _async_es_class  # type: ignore[attr-defined]
sys.modules.setdefault("elasticsearch", _es_module)

from mp_commons.adapters.elasticsearch.client import (
    ElasticsearchClient,
    ElasticsearchRepository,
    ElasticsearchSearchQuery,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_client() -> tuple[ElasticsearchClient, MagicMock]:
    mock_inner = MagicMock()
    mock_inner.index = AsyncMock()
    mock_inner.get = AsyncMock(return_value={"_source": {"id": "1", "name": "Alice"}})
    mock_inner.delete = AsyncMock()
    mock_inner.search = AsyncMock(
        return_value={"hits": {"hits": [{"_source": {"id": "1", "name": "Alice"}}]}}
    )
    mock_inner.close = AsyncMock()
    _async_es_class.return_value = mock_inner
    client = ElasticsearchClient("http://localhost:9200", index_prefix="test_")
    return client, mock_inner


# ---------------------------------------------------------------------------
# ElasticsearchSearchQuery
# ---------------------------------------------------------------------------


def test_query_build_match_all():
    q = ElasticsearchSearchQuery()
    dsl = q.build()
    assert dsl["query"] == {"match_all": {}}
    assert dsl["from"] == 0
    assert dsl["size"] == 10


def test_query_must_clause():
    q = ElasticsearchSearchQuery().must("status", "active")
    dsl = q.build()
    assert {"term": {"status": "active"}} in dsl["query"]["bool"]["must"]


def test_query_should_clause():
    q = ElasticsearchSearchQuery().should("type", "admin")
    dsl = q.build()
    assert {"term": {"type": "admin"}} in dsl["query"]["bool"]["should"]


def test_query_range_clause():
    q = ElasticsearchSearchQuery().range("age", gte=18, lte=65)
    dsl = q.build()
    assert {"range": {"age": {"gte": 18, "lte": 65}}} in dsl["query"]["bool"]["must"]


def test_query_sort():
    q = ElasticsearchSearchQuery().sort("name", "asc")
    dsl = q.build()
    assert dsl["sort"] == [{"name": {"order": "asc"}}]


def test_query_paginate():
    q = ElasticsearchSearchQuery().paginate(page=3, size=10)
    dsl = q.build()
    assert dsl["from"] == 20
    assert dsl["size"] == 10


def test_query_chaining():
    q = (
        ElasticsearchSearchQuery()
        .must("status", "active")
        .range("score", gte=50)
        .sort("score", "desc")
        .paginate(2, 5)
    )
    dsl = q.build()
    assert dsl["from"] == 5
    assert dsl["size"] == 5
    assert dsl["sort"] == [{"score": {"order": "desc"}}]


# ---------------------------------------------------------------------------
# ElasticsearchClient
# ---------------------------------------------------------------------------


def test_client_index_calls_inner():
    client, mock_inner = _make_client()

    async def run():
        await client.index("1", {"name": "Alice"}, index="users")

    import asyncio

    asyncio.run(run())
    mock_inner.index.assert_called_once_with(index="test_users", id="1", document={"name": "Alice"})


def test_client_get_returns_source():
    client, _mock_inner = _make_client()

    async def run():
        return await client.get("1", index="users")

    result = __import__("asyncio").run(run())
    assert result == {"id": "1", "name": "Alice"}


def test_client_get_returns_none_on_not_found():
    client, mock_inner = _make_client()
    mock_inner.get = AsyncMock(side_effect=_FakeNotFoundError("404 Not Found"))

    async def run():
        return await client.get("missing", index="users")

    result = __import__("asyncio").run(run())
    assert result is None


def test_client_delete_calls_inner():
    client, mock_inner = _make_client()

    async def run():
        await client.delete("1", index="users")

    __import__("asyncio").run(run())
    mock_inner.delete.assert_called_once()


def test_client_search_returns_sources():
    client, _mock_inner = _make_client()

    async def run():
        return await client.search({"query": {"match_all": {}}}, index="users")

    result = __import__("asyncio").run(run())
    assert result == [{"id": "1", "name": "Alice"}]


def test_client_close():
    client, mock_inner = _make_client()
    __import__("asyncio").run(client.close())
    mock_inner.close.assert_called_once()


# ---------------------------------------------------------------------------
# ElasticsearchRepository
# ---------------------------------------------------------------------------


import dataclasses


@dataclasses.dataclass
class _User:
    id: str
    name: str


def test_repository_find_by_id():
    client, _mock_inner = _make_client()
    repo = ElasticsearchRepository(client, "users", _User)

    result = __import__("asyncio").run(repo.find_by_id("1"))
    assert isinstance(result, _User)
    assert result.name == "Alice"


def test_repository_find_by_id_not_found():
    client, mock_inner = _make_client()
    mock_inner.get = AsyncMock(return_value={"_source": None})
    # If None source, model(**None) would fail. Test the not-found path:
    mock_inner.get = AsyncMock(side_effect=_FakeNotFoundError("404"))
    repo = ElasticsearchRepository(client, "users", _User)

    result = __import__("asyncio").run(repo.find_by_id("missing"))
    assert result is None


def test_repository_save():
    client, mock_inner = _make_client()
    repo = ElasticsearchRepository(client, "users", _User)
    user = _User(id="42", name="Bob")

    __import__("asyncio").run(repo.save(user))
    mock_inner.index.assert_called_once_with(index="test_users", id="42", document={"name": "Bob"})


def test_repository_search():
    client, mock_inner = _make_client()
    repo = ElasticsearchRepository(client, "users", _User)
    mock_inner.search = AsyncMock(
        return_value={"hits": {"hits": [{"_source": {"id": "1", "name": "Alice"}}]}}
    )

    results = __import__("asyncio").run(repo.search({"query": {"match_all": {}}}))
    assert len(results) == 1
    assert results[0].name == "Alice"


def test_repository_delete():
    client, mock_inner = _make_client()
    repo = ElasticsearchRepository(client, "users", _User)

    __import__("asyncio").run(repo.delete("1"))
    mock_inner.delete.assert_called_once()
