"""Unit tests for OpenSearch adapter (A-10)."""
from __future__ import annotations

import dataclasses
import sys
import types
from unittest.mock import AsyncMock, MagicMock

import pytest

# ---------------------------------------------------------------------------
# Stub opensearchpy so tests run without the real library
# ---------------------------------------------------------------------------

_os_module = types.ModuleType("opensearchpy")
_async_os_class = MagicMock(name="AsyncOpenSearch")
_os_module.AsyncOpenSearch = _async_os_class  # type: ignore[attr-defined]
sys.modules.setdefault("opensearchpy", _os_module)

from mp_commons.adapters.opensearch.client import (  # noqa: E402
    OpenSearchClient,
    OpenSearchRepository,
    OpenSearchSearchQuery,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_client() -> tuple[OpenSearchClient, MagicMock]:
    mock_inner = MagicMock()
    mock_inner.index = AsyncMock()
    mock_inner.get = AsyncMock(return_value={"_source": {"id": "doc-1", "name": "Alice"}})
    mock_inner.delete = AsyncMock()
    mock_inner.search = AsyncMock(
        return_value={"hits": {"hits": [{"_source": {"id": "doc-1", "name": "Alice"}}]}}
    )
    mock_inner.close = AsyncMock()
    _async_os_class.return_value = mock_inner
    client = OpenSearchClient("http://localhost:9200", index_prefix="test_")
    return client, mock_inner


@dataclasses.dataclass
class _Doc:
    id: str
    name: str


# ---------------------------------------------------------------------------
# OpenSearchSearchQuery
# ---------------------------------------------------------------------------


class TestSearchQuery:
    def test_build_match_all(self):
        q = OpenSearchSearchQuery()
        assert q.build()["query"] == {"match_all": {}}

    def test_must_clause(self):
        q = OpenSearchSearchQuery().must("status", "active")
        dsl = q.build()
        assert {"term": {"status": "active"}} in dsl["query"]["bool"]["must"]

    def test_should_clause(self):
        q = OpenSearchSearchQuery().should("tag", "news")
        dsl = q.build()
        assert {"term": {"tag": "news"}} in dsl["query"]["bool"]["should"]

    def test_range_clause(self):
        q = OpenSearchSearchQuery().range("age", gte=18, lte=65)
        dsl = q.build()
        assert {"range": {"age": {"gte": 18, "lte": 65}}} in dsl["query"]["bool"]["must"]

    def test_sort_clause(self):
        q = OpenSearchSearchQuery().sort("name", "desc")
        dsl = q.build()
        assert dsl["sort"] == [{"name": {"order": "desc"}}]

    def test_paginate(self):
        q = OpenSearchSearchQuery().paginate(page=2, size=10)
        dsl = q.build()
        assert dsl["from"] == 10
        assert dsl["size"] == 10

    def test_chaining(self):
        q = (
            OpenSearchSearchQuery()
            .must("status", "active")
            .sort("created_at", "desc")
            .paginate(page=1, size=5)
        )
        dsl = q.build()
        assert dsl["size"] == 5


# ---------------------------------------------------------------------------
# OpenSearchClient
# ---------------------------------------------------------------------------


class TestOpenSearchClient:
    @pytest.mark.asyncio
    async def test_index_uses_prefix(self):
        client, inner = _make_client()
        await client.index("doc-1", {"name": "Bob"}, index="users")
        inner.index.assert_called_once_with(index="test_users", id="doc-1", body={"name": "Bob"})

    @pytest.mark.asyncio
    async def test_get_returns_source(self):
        client, _ = _make_client()
        doc = await client.get("doc-1", index="users")
        assert doc == {"id": "doc-1", "name": "Alice"}

    @pytest.mark.asyncio
    async def test_get_returns_none_on_not_found(self):
        client, inner = _make_client()
        inner.get.side_effect = Exception("404 not found")
        result = await client.get("missing", index="users")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_calls_inner(self):
        client, inner = _make_client()
        await client.delete("doc-1", index="users")
        inner.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_handles_not_found(self):
        client, inner = _make_client()
        inner.delete.side_effect = Exception("NotFoundError")
        await client.delete("missing", index="users")  # must not raise

    @pytest.mark.asyncio
    async def test_search_returns_sources(self):
        client, _ = _make_client()
        results = await client.search({"query": {"match_all": {}}}, index="users")
        assert results == [{"id": "doc-1", "name": "Alice"}]

    @pytest.mark.asyncio
    async def test_close_called_on_exit(self):
        client, inner = _make_client()
        async with client:
            pass
        inner.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_missing_opensearch_raises(self):
        import mp_commons.adapters.opensearch.client as mod
        from unittest.mock import patch

        with patch.object(mod, "_require_opensearch", side_effect=ImportError("no os")):
            with pytest.raises(ImportError):
                OpenSearchClient("http://localhost:9200")


# ---------------------------------------------------------------------------
# OpenSearchRepository
# ---------------------------------------------------------------------------


class TestOpenSearchRepository:
    @pytest.mark.asyncio
    async def test_find_by_id_returns_model(self):
        client, _ = _make_client()
        repo = OpenSearchRepository(client, "users", _Doc)
        doc = await repo.find_by_id("doc-1")
        assert isinstance(doc, _Doc)
        assert doc.name == "Alice"

    @pytest.mark.asyncio
    async def test_find_by_id_returns_none_when_missing(self):
        client, inner = _make_client()
        inner.get.side_effect = Exception("404")
        repo = OpenSearchRepository(client, "users", _Doc)
        result = await repo.find_by_id("missing")
        assert result is None

    @pytest.mark.asyncio
    async def test_save_indexes_document(self):
        client, inner = _make_client()
        repo = OpenSearchRepository(client, "users", _Doc)
        doc = _Doc(id="doc-2", name="Bob")
        await repo.save(doc)
        inner.index.assert_called_once()
        call_kwargs = inner.index.call_args[1]
        assert call_kwargs["id"] == "doc-2"
        assert call_kwargs["body"]["name"] == "Bob"

    @pytest.mark.asyncio
    async def test_search_returns_models(self):
        client, _ = _make_client()
        repo = OpenSearchRepository(client, "users", _Doc)
        results = await repo.search({"query": {"match_all": {}}})
        assert len(results) == 1
        assert isinstance(results[0], _Doc)

    @pytest.mark.asyncio
    async def test_delete_removes_document(self):
        client, inner = _make_client()
        repo = OpenSearchRepository(client, "users", _Doc)
        await repo.delete("doc-1")
        inner.delete.assert_called_once()
