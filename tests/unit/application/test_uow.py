"""Unit tests for Application UnitOfWork — §14."""

from __future__ import annotations

import asyncio

import pytest

from mp_commons.application.uow import TransactionManager, UnitOfWork, transactional
from mp_commons.kernel.errors import DomainError


# ---------------------------------------------------------------------------
# TransactionManager stub (14.1)
# ---------------------------------------------------------------------------


class InMemoryTransactionManager(TransactionManager):
    def __init__(self) -> None:
        self.began = False
        self.committed = False
        self.rolled_back = False

    async def begin(self) -> None:
        self.began = True

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


class TestTransactionManager:
    def test_begin_commit(self) -> None:
        tm = InMemoryTransactionManager()

        async def _run() -> None:
            await tm.begin()
            await tm.commit()

        asyncio.run(_run())
        assert tm.began is True
        assert tm.committed is True
        assert tm.rolled_back is False

    def test_begin_rollback(self) -> None:
        tm = InMemoryTransactionManager()

        async def _run() -> None:
            await tm.begin()
            await tm.rollback()

        asyncio.run(_run())
        assert tm.began is True
        assert tm.rolled_back is True
        assert tm.committed is False


# ---------------------------------------------------------------------------
# UnitOfWork async context manager (14.1)
# ---------------------------------------------------------------------------


class InMemoryUnitOfWork:
    """Simple in-memory UoW that tracks enter/exit."""

    def __init__(self) -> None:
        self.entered = False
        self.committed = False
        self.rolled_back = False

    async def __aenter__(self) -> "InMemoryUnitOfWork":
        self.entered = True
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[type-arg]
        if exc_type is None:
            self.committed = True
        else:
            self.rolled_back = True


class TestUnitOfWork:
    def test_enter_commits_on_success(self) -> None:
        uow = InMemoryUnitOfWork()

        async def _run() -> None:
            async with uow:
                pass

        asyncio.run(_run())
        assert uow.entered is True
        assert uow.committed is True
        assert uow.rolled_back is False

    def test_enter_rolls_back_on_error(self) -> None:
        uow = InMemoryUnitOfWork()

        async def _run() -> None:
            try:
                async with uow:
                    raise DomainError("boom")
            except DomainError:
                pass

        asyncio.run(_run())
        assert uow.rolled_back is True
        assert uow.committed is False


# ---------------------------------------------------------------------------
# @transactional decorator (14.2)
# ---------------------------------------------------------------------------


class TestTransactionalDecorator:
    def test_commit_on_success(self) -> None:
        uow = InMemoryUnitOfWork()

        class Service:
            _uow = uow

            @transactional()
            async def do_work(self) -> str:
                return "done"

        result = asyncio.run(Service().do_work())
        assert result == "done"
        assert uow.committed is True

    def test_rollback_on_exception(self) -> None:
        uow = InMemoryUnitOfWork()

        class Service:
            _uow = uow

            @transactional()
            async def do_work(self) -> None:
                raise DomainError("failure")

        with pytest.raises(DomainError):
            asyncio.run(Service().do_work())

        assert uow.rolled_back is True

    def test_no_uow_passes_through(self) -> None:
        """If no _uow attribute exists, the function runs without a transaction."""

        class Service:
            @transactional()
            async def do_work(self) -> str:
                return "no uow"

        result = asyncio.run(Service().do_work())
        assert result == "no uow"

    def test_custom_attribute_name(self) -> None:
        uow = InMemoryUnitOfWork()

        class Service:
            my_uow = uow

            @transactional(uow_attribute="my_uow")
            async def do_work(self) -> str:
                return "custom"

        result = asyncio.run(Service().do_work())
        assert result == "custom"
        assert uow.committed is True


# ---------------------------------------------------------------------------
# Public surface smoke test
# ---------------------------------------------------------------------------


class TestPublicReExports:
    def test_all_symbols_importable(self) -> None:
        import importlib

        mod = importlib.import_module("mp_commons.application.uow")
        for name in mod.__all__:
            assert hasattr(mod, name), f"{name!r} missing"
