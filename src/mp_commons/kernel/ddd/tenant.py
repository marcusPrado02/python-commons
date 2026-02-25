"""Multi-tenancy context and resolver port."""

from __future__ import annotations

import contextlib
from contextvars import ContextVar
from typing import AsyncIterator, Protocol, Any

from mp_commons.kernel.errors.domain import ValidationError
from mp_commons.kernel.types.ids import TenantId

_TENANT_CTX_VAR: ContextVar[TenantId | None] = ContextVar(
    "_mp_tenant_ctx", default=None
)


class TenantContext:
    """Ambient tenant context using ``contextvars``."""

    @staticmethod
    def set(tenant_id: TenantId) -> Any:
        return _TENANT_CTX_VAR.set(tenant_id)

    @staticmethod
    def get() -> TenantId | None:
        return _TENANT_CTX_VAR.get()

    @staticmethod
    def require() -> TenantId:
        tenant = _TENANT_CTX_VAR.get()
        if tenant is None:
            raise ValidationError("No tenant in context")
        return tenant

    @staticmethod
    def reset(token: Any) -> None:
        _TENANT_CTX_VAR.reset(token)

    @staticmethod
    def clear() -> None:
        _TENANT_CTX_VAR.set(None)

    @staticmethod
    @contextlib.asynccontextmanager
    async def scoped(tenant_id: TenantId) -> AsyncIterator[None]:
        """Async context manager — sets *tenant_id* for the duration of the block.

        The previous tenant (if any) is restored on exit, even on error.

        Example::

            async with TenantContext.scoped(TenantId("acme")):
                result = await use_case.execute(cmd)
        """
        token = _TENANT_CTX_VAR.set(tenant_id)
        try:
            yield
        finally:
            _TENANT_CTX_VAR.reset(token)


class TenantResolver(Protocol):
    """Port: resolves a TenantId from a raw request token / header."""

    async def resolve(self, raw_token: str) -> TenantId: ...


# ---------------------------------------------------------------------------
# TenantAware mixin
# ---------------------------------------------------------------------------

class TenantAware:
    """Mixin that stores a ``tenant_id`` attribute.

    When ``tenant_id`` is not provided on construction the value is
    auto-populated from ``TenantContext.require()``.

    Usage::

        class Order(TenantAware, Entity):
            def __init__(self, id: EntityId, amount: Money, tenant_id: TenantId | None = None) -> None:
                super().__init__(id)
                self._init_tenant(tenant_id)
    """

    tenant_id: TenantId

    def _init_tenant(self, tenant_id: TenantId | None = None) -> None:
        """Call from ``__init__`` to set ``self.tenant_id``."""
        self.tenant_id = tenant_id if tenant_id is not None else TenantContext.require()


__all__ = ["TenantAware", "TenantContext", "TenantResolver"]
