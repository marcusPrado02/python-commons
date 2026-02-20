"""Multi-tenancy context and resolver port."""

from __future__ import annotations

from contextvars import ContextVar
from typing import Protocol, Any

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


class TenantResolver(Protocol):
    """Port: resolves a TenantId from a raw request token / header."""

    async def resolve(self, raw_token: str) -> TenantId: ...


__all__ = ["TenantContext", "TenantResolver"]
