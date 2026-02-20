"""Testing fixtures – tenant_fixture."""
from __future__ import annotations

try:
    import pytest

    @pytest.fixture
    def tenant_fixture():
        from mp_commons.kernel.ddd import TenantContext
        from mp_commons.kernel.types import TenantId
        tenant_id = TenantId("test-tenant")
        token = TenantContext.set(tenant_id)
        yield tenant_id
        TenantContext.reset(token)

except ImportError:
    pass

__all__ = ["tenant_fixture"]
