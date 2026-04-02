"""Integration tests for Elasticsearch adapter (§48.6 / B-03).

Uses testcontainers to spin up a real Elasticsearch node.
Run with: pytest tests/integration/test_elasticsearch.py -m integration -v

Requires Docker.  The ES container exposes port 9200.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import pytest
from testcontainers.elasticsearch import ElasticSearchContainer

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _run(coro: Any) -> Any:  # type: ignore[no-untyped-def]
    return asyncio.run(coro)


@pytest.fixture(scope="module")
def es_url() -> str:  # type: ignore[return]
    with ElasticSearchContainer("elasticsearch:8.13.0", mem_limit="1g") as es:
        # Wait until ES is ready (it takes a few seconds after port is open)
        host = es.get_container_host_ip()
        port = es.get_exposed_port(9200)
        url = f"http://{host}:{port}"
        _wait_es_ready(url)
        yield url


def _wait_es_ready(url: str, timeout: int = 60) -> None:
    import urllib.request

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{url}/_cluster/health", timeout=2) as r:
                if r.status == 200:
                    return
        except Exception:
            pass
        time.sleep(1)
    raise TimeoutError(f"Elasticsearch did not become ready at {url} within {timeout}s")


# ---------------------------------------------------------------------------
# §48.6 — ElasticsearchClient / ElasticsearchRepository
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestElasticsearchClientIntegration:
    """Round-trip tests against a real Elasticsearch container."""

    def test_index_and_get(self, es_url: str) -> None:
        from mp_commons.adapters.elasticsearch import ElasticsearchClient

        client = ElasticsearchClient(url=es_url)

        async def _run_test() -> None:
            async with client:
                await client.index("doc-1", {"title": "hello", "score": 10}, index="test")
                result = await client.get("doc-1", index="test")
                assert result is not None
                assert result["title"] == "hello"
                assert result["score"] == 10

        _run(_run_test())

    def test_delete_removes_document(self, es_url: str) -> None:
        from mp_commons.adapters.elasticsearch import ElasticsearchClient

        client = ElasticsearchClient(url=es_url)

        async def _run_test() -> None:
            async with client:
                await client.index("doc-del", {"x": 1}, index="test")
                await client.delete("doc-del", index="test")
                result = await client.get("doc-del", index="test")
                assert result is None

        _run(_run_test())

    def test_get_missing_returns_none(self, es_url: str) -> None:
        from mp_commons.adapters.elasticsearch import ElasticsearchClient

        client = ElasticsearchClient(url=es_url)

        async def _run_test() -> None:
            async with client:
                result = await client.get("nonexistent-doc", index="test")
                assert result is None

        _run(_run_test())

    def test_dsl_search_returns_matching_docs_only(self, es_url: str) -> None:
        from mp_commons.adapters.elasticsearch import (
            ElasticsearchClient,
            ElasticsearchSearchQuery,
        )

        client = ElasticsearchClient(url=es_url)

        async def _run_test() -> None:
            async with client:
                await client.index(
                    "search-1", {"category": "fruit", "name": "apple"}, index="search-test"
                )
                await client.index(
                    "search-2", {"category": "fruit", "name": "banana"}, index="search-test"
                )
                await client.index(
                    "search-3", {"category": "veggie", "name": "carrot"}, index="search-test"
                )
                # ES needs a moment to refresh before search reflects new docs
                await asyncio.sleep(2)

                query = ElasticsearchSearchQuery().must("category", "fruit").build()
                results = await client.search(query, index="search-test")
                names = {r["name"] for r in results}
                assert "apple" in names
                assert "banana" in names
                assert "carrot" not in names

        _run(_run_test())
