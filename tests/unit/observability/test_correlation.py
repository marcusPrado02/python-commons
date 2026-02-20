"""Unit tests for CorrelationContext."""

from __future__ import annotations

import asyncio

import pytest

from mp_commons.observability.correlation import CorrelationContext, RequestContext
from mp_commons.kernel.types import CorrelationId, TenantId


class TestCorrelationContext:
    def setup_method(self) -> None:
        CorrelationContext.clear()

    def test_set_and_get(self) -> None:
        ctx = RequestContext.new()
        CorrelationContext.set(ctx)
        assert CorrelationContext.get() is ctx

    def test_get_returns_none_when_unset(self) -> None:
        assert CorrelationContext.get() is None

    def test_require_raises_when_unset(self) -> None:
        with pytest.raises(RuntimeError):
            CorrelationContext.require()

    def test_require_returns_context_when_set(self) -> None:
        ctx = RequestContext.new()
        CorrelationContext.set(ctx)
        assert CorrelationContext.require() is ctx

    def test_get_or_new_creates_when_unset(self) -> None:
        ctx = CorrelationContext.get_or_new()
        assert ctx is not None
        assert ctx.correlation_id is not None

    def test_get_or_new_returns_existing(self) -> None:
        ctx = RequestContext.new()
        CorrelationContext.set(ctx)
        assert CorrelationContext.get_or_new() is ctx

    def test_clear_removes_context(self) -> None:
        CorrelationContext.set(RequestContext.new())
        CorrelationContext.clear()
        assert CorrelationContext.get() is None

    def test_isolated_across_tasks(self) -> None:
        """Each asyncio task should have its own context."""
        results: list[str | None] = []

        async def worker(cid: str) -> None:
            ctx = RequestContext(correlation_id=CorrelationId(cid))
            CorrelationContext.set(ctx)
            await asyncio.sleep(0)
            stored = CorrelationContext.get()
            results.append(stored.correlation_id.value if stored else None)

        async def run() -> None:
            await asyncio.gather(worker("id-1"), worker("id-2"))

        asyncio.run(run())
        assert set(results) == {"id-1", "id-2"}


class TestRequestContext:
    def test_new_generates_unique_ids(self) -> None:
        a = RequestContext.new()
        b = RequestContext.new()
        assert a.correlation_id != b.correlation_id

    def test_with_tenant(self) -> None:
        ctx = RequestContext.new(tenant_id=TenantId("t1"))
        assert ctx.tenant_id == TenantId("t1")
