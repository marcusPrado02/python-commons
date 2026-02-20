"""Unit tests for pagination primitives — §11."""

from __future__ import annotations

import pytest

from mp_commons.application.pagination import (
    CursorPage,
    Page,
    PageRequest,
    Sort,
    SortDirection,
)


# ---------------------------------------------------------------------------
# PageRequest (11.1)
# ---------------------------------------------------------------------------


class TestPageRequest:
    def test_defaults(self) -> None:
        pr = PageRequest()
        assert pr.page == 1
        assert pr.size == 20

    def test_offset(self) -> None:
        pr = PageRequest(page=3, size=10)
        assert pr.offset == 20  # (3-1)*10

    def test_page_zero_raises(self) -> None:
        with pytest.raises(ValueError):
            PageRequest(page=0)

    def test_size_zero_raises(self) -> None:
        with pytest.raises(ValueError):
            PageRequest(size=0)

    def test_sorts_attached(self) -> None:
        pr = PageRequest(sorts=(Sort("name", SortDirection.DESC),))
        assert pr.sorts[0].field == "name"
        assert pr.sorts[0].direction == SortDirection.DESC

    def test_second_page_offset(self) -> None:
        assert PageRequest(page=2, size=5).offset == 5

    def test_size_max_raises(self) -> None:
        with pytest.raises(ValueError):
            PageRequest(size=1001)


# ---------------------------------------------------------------------------
# Page (11.2)
# ---------------------------------------------------------------------------


class TestPage:
    def test_of_slices_items(self) -> None:
        items = list(range(100))
        pr = PageRequest(page=2, size=10)
        page = Page.of(items, pr)
        assert page.items == list(range(10, 20))
        assert page.total == 100
        assert page.page == 2

    def test_total_pages(self) -> None:
        page = Page.of(list(range(25)), PageRequest(page=1, size=10))
        assert page.total_pages == 3

    def test_total_pages_exact_division(self) -> None:
        page = Page.of(list(range(20)), PageRequest(page=1, size=10))
        assert page.total_pages == 2

    def test_has_next(self) -> None:
        page = Page.of(list(range(25)), PageRequest(page=1, size=10))
        assert page.has_next

    def test_no_next_on_last_page(self) -> None:
        page = Page.of(list(range(25)), PageRequest(page=3, size=10))
        assert not page.has_next

    def test_has_previous(self) -> None:
        page = Page.of(list(range(25)), PageRequest(page=2, size=10))
        assert page.has_previous

    def test_no_previous_on_first_page(self) -> None:
        page = Page.of(list(range(25)), PageRequest(page=1, size=10))
        assert not page.has_previous

    def test_last_page_partial(self) -> None:
        page = Page.of(list(range(25)), PageRequest(page=3, size=10))
        assert len(page.items) == 5

    def test_empty_list(self) -> None:
        page = Page.of([], PageRequest(page=1, size=10))
        assert page.items == []
        assert page.total == 0
        assert page.total_pages == 0

    def test_map_transforms_items(self) -> None:
        page = Page.of(list(range(5)), PageRequest(page=1, size=5))
        doubled = page.map(lambda x: x * 2)
        assert doubled.items == [0, 2, 4, 6, 8]
        assert doubled.total == 5
        assert doubled.page == 1

    def test_map_preserves_pagination(self) -> None:
        page = Page.of(list(range(30)), PageRequest(page=2, size=10))
        mapped = page.map(str)
        assert mapped.page == 2
        assert mapped.size == 10
        assert mapped.total == 30


# ---------------------------------------------------------------------------
# CursorPage (11.3)
# ---------------------------------------------------------------------------


class TestCursorPage:
    def test_defaults(self) -> None:
        page: CursorPage[int] = CursorPage(items=[1, 2, 3])
        assert page.has_more is False
        assert page.next_cursor is None

    def test_with_cursor(self) -> None:
        page: CursorPage[str] = CursorPage(
            items=["a", "b"], next_cursor="tok123", has_more=True
        )
        assert page.has_more is True
        assert page.next_cursor == "tok123"

    def test_frozen(self) -> None:
        page: CursorPage[int] = CursorPage(items=[])
        with pytest.raises((AttributeError, TypeError)):
            page.has_more = True  # type: ignore[misc]

    def test_empty(self) -> None:
        page: CursorPage[int] = CursorPage(items=[], has_more=False)
        assert page.items == []


# ---------------------------------------------------------------------------
# Public surface smoke test
# ---------------------------------------------------------------------------


class TestPublicReExports:
    def test_all_symbols_importable(self) -> None:
        import importlib

        mod = importlib.import_module("mp_commons.application.pagination")
        for name in mod.__all__:
            assert hasattr(mod, name), f"{name!r} missing from pagination"
