"""Unit tests for TenantIsolationValidator (S-01)."""
from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock

import pytest

from mp_commons.testing.tenant_isolation import TenantIsolationValidator, TenantLeakError


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


@dataclass
class _Order:
    id: str
    tenant_id: str
    amount: float


class _FakeOrderRepo:
    def __init__(self, orders: list[_Order]) -> None:
        self._orders = orders

    async def find_all(self) -> list[_Order]:
        return self._orders

    async def find_by_id(self, order_id: str) -> _Order | None:
        return next((o for o in self._orders if o.id == order_id), None)

    async def count(self) -> int:
        return len(self._orders)

    def some_attr(self) -> str:
        return "value"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestTenantIsolationValidator:
    def _make_repo(self, orders: list[_Order]) -> TenantIsolationValidator:
        return TenantIsolationValidator(_FakeOrderRepo(orders), tenant_id="acme")

    async def test_passes_when_all_same_tenant(self):
        orders = [_Order("1", "acme", 10.0), _Order("2", "acme", 20.0)]
        validator = self._make_repo(orders)
        result = await validator.find_all()
        assert result == orders

    async def test_raises_on_cross_tenant_list(self):
        orders = [
            _Order("1", "acme", 10.0),
            _Order("2", "other-org", 20.0),  # leaked
        ]
        validator = self._make_repo(orders)
        with pytest.raises(TenantLeakError) as exc_info:
            await validator.find_all()
        assert exc_info.value.expected_tenant == "acme"
        assert "other-org" in exc_info.value.leaked_tenants

    async def test_passes_for_single_item_same_tenant(self):
        orders = [_Order("1", "acme", 10.0)]
        validator = self._make_repo(orders)
        result = await validator.find_by_id("1")
        assert result is not None

    async def test_raises_for_single_item_wrong_tenant(self):
        orders = [_Order("1", "evil-corp", 10.0)]
        validator = self._make_repo(orders)
        with pytest.raises(TenantLeakError):
            await validator.find_by_id("1")

    async def test_passes_for_none_result(self):
        validator = self._make_repo([])
        result = await validator.find_by_id("nonexistent")
        assert result is None

    async def test_passes_for_results_without_tenant_attr(self):
        """Objects without tenant_id attribute are not validated."""
        orders = [_Order("1", "acme", 10.0)]
        validator = self._make_repo(orders)
        count = await validator.count()  # returns int, no tenant_id
        assert count == 1

    def test_non_callable_attr_proxied(self):
        validator = TenantIsolationValidator(_FakeOrderRepo([]), tenant_id="acme")
        # sync callable also works
        result = validator.some_attr()
        assert result == "value"

    async def test_error_message_includes_count(self):
        orders = [
            _Order("1", "other-org", 1.0),
            _Order("2", "other-org", 2.0),
        ]
        validator = self._make_repo(orders)
        with pytest.raises(TenantLeakError, match="found 2 result"):
            await validator.find_all()

    async def test_custom_tenant_attr(self):
        @dataclass
        class _Doc:
            id: str
            org: str  # custom tenant attribute name

        class _DocRepo:
            async def all(self) -> list[_Doc]:
                return [_Doc("1", "other")]

        validator = TenantIsolationValidator(_DocRepo(), tenant_id="mine", attr="org")
        with pytest.raises(TenantLeakError):
            await validator.all()
