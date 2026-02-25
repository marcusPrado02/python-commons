"""Unit tests for §70 – Search Abstraction."""
import asyncio

import pytest

from mp_commons.application.search import (
    Filter,
    InMemorySearchEngine,
    SearchQuery,
    SearchResult,
    SortField,
)


def _make_engine():
    items = [
        {"id": "1", "name": "Red Shoes", "price": 50, "brand": "Nike"},
        {"id": "2", "name": "Blue Bag", "price": 120, "brand": "Adidas"},
        {"id": "3", "name": "Red Hat", "price": 30, "brand": "Nike"},
        {"id": "4", "name": "Green Jacket", "price": 200, "brand": "Puma"},
    ]
    return InMemorySearchEngine(items, key_fn=lambda x: x)


class TestInMemorySearchEngineText:
    def test_term_match_case_insensitive(self):
        engine = _make_engine()
        q = SearchQuery(terms="red")
        result = asyncio.run(engine.search(q))
        assert result.total == 2
        ids = {i["id"] for i in result.items}
        assert ids == {"1", "3"}

    def test_no_terms_returns_all(self):
        engine = _make_engine()
        q = SearchQuery(terms="")
        result = asyncio.run(engine.search(q))
        assert result.total == 4

    def test_no_match_empty_result(self):
        engine = _make_engine()
        q = SearchQuery(terms="XYZ_NONE")
        result = asyncio.run(engine.search(q))
        assert result.total == 0
        assert result.items == []


class TestInMemorySearchEngineFilters:
    def test_filter_eq(self):
        engine = _make_engine()
        q = SearchQuery(filters=[Filter(field="brand", value="Nike")])
        result = asyncio.run(engine.search(q))
        assert result.total == 2

    def test_filter_gt(self):
        engine = _make_engine()
        q = SearchQuery(filters=[Filter(field="price", value=100, op="gt")])
        result = asyncio.run(engine.search(q))
        assert result.total == 2

    def test_filter_lte(self):
        engine = _make_engine()
        q = SearchQuery(filters=[Filter(field="price", value=50, op="lte")])
        result = asyncio.run(engine.search(q))
        assert result.total == 2  # price 50 and 30

    def test_filter_in(self):
        engine = _make_engine()
        q = SearchQuery(filters=[Filter(field="brand", value=["Nike", "Puma"], op="in")])
        result = asyncio.run(engine.search(q))
        assert result.total == 3

    def test_filter_contains(self):
        engine = _make_engine()
        q = SearchQuery(filters=[Filter(field="name", value="Bag", op="contains")])
        result = asyncio.run(engine.search(q))
        assert result.total == 1


class TestInMemorySearchEngineSortPagination:
    def test_sort_asc(self):
        engine = _make_engine()
        q = SearchQuery(sort=[SortField(field="price", direction="asc")])
        result = asyncio.run(engine.search(q))
        prices = [i["price"] for i in result.items]
        assert prices == sorted(prices)

    def test_sort_desc(self):
        engine = _make_engine()
        q = SearchQuery(sort=[SortField(field="price", direction="desc")])
        result = asyncio.run(engine.search(q))
        prices = [i["price"] for i in result.items]
        assert prices == sorted(prices, reverse=True)

    def test_pagination_page2(self):
        engine = _make_engine()
        q = SearchQuery(page=2, page_size=2)
        result = asyncio.run(engine.search(q))
        assert result.page == 2
        assert len(result.items) == 2

    def test_total_pages(self):
        engine = _make_engine()
        q = SearchQuery(page=1, page_size=3)
        result = asyncio.run(engine.search(q))
        assert result.total_pages == 2

    def test_has_next(self):
        engine = _make_engine()
        q = SearchQuery(page=1, page_size=3)
        result = asyncio.run(engine.search(q))
        assert result.has_next is True
        q2 = SearchQuery(page=2, page_size=3)
        result2 = asyncio.run(engine.search(q2))
        assert result2.has_next is False


class TestInMemorySearchEngineSuggest:
    def test_suggest_prefix(self):
        engine = _make_engine()
        suggestions = asyncio.run(engine.suggest("Re", "name"))
        assert any("Red" in s for s in suggestions)

    def test_suggest_empty(self):
        engine = _make_engine()
        suggestions = asyncio.run(engine.suggest("ZZZNONE", "name"))
        assert suggestions == []
