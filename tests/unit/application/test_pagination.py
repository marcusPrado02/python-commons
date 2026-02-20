"""Unit tests for pagination primitives."""

from __future__ import annotations

import pytest

from mp_commons.application.pagination import Page, PageRequest, Sort, SortDirection


class TestPageRequest:
    def test_defaults(self) -> None:
        pr = PageRequest()
        assert pr.page == 1
        assert pr.size == 20

    def test_offset(self) -> None:
        pr = PageRequest(page=3, size=10)
        assert pr.offset == 20  # (3-1)*10

    def test_page_zero_raises(self) -> None:
        with pytest.raises((ValueError, Exception)):
            PageRequest(page=0)

    def test_size_zero_raises(self) -> None:
        with pytest.raises((ValueError, Exception)):
            PageRequest(size=0)

    def test_sort_attached(self) -> None:
        pr = PageRequest(sort=[Sort("name", SortDirection.DESC)])
        assert pr.sort[0].field == "name"
        assert pr.sort[0].direction == SortDirection.DESC


class TestPage:
    def test_page_of_slices_items(self) -> None:
        items = list(range(100))
        pr = PageRequest(page=2, size=10)
        page = Page.of(items, pr)
        assert page.items == list(range(10, 20))
        assert page.total == 100
        assert page.page == 2

    def test_total_pages(self) -> None:
        page = Page.of(list(range(25)), PageRequest(page=1, size=10))
        assert page.total_pages == 3

    def test_has_next(self) -> None:
        page = Page.of(list(range(25)), PageRequest(page=1, size=10))
        assert page.has_next

    def test_no_next_on_last_page(self) -> None:
        page = Page.of(list(range(25)), PageRequest(page=3, size=10))
        assert not page.has_next

    def test_last_page_partial(self) -> None:
        page = Page.of(list(range(25)), PageRequest(page=3, size=10))
        assert len(page.items) == 5

    def test_empty_list(self) -> None:
        page = Page.of([], PageRequest(page=1, size=10))
        assert page.items == []
        assert page.total == 0
        assert page.total_pages == 0
