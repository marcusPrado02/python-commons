"""Testing fixtures – correlation_fixture."""
from __future__ import annotations

try:
    import pytest

    @pytest.fixture
    def correlation_fixture():
        from mp_commons.observability.correlation import CorrelationContext, RequestContext
        ctx = RequestContext(correlation_id="test-correlation-id", tenant_id="tenant-1")
        CorrelationContext.set(ctx)
        yield ctx
        CorrelationContext.clear()

except ImportError:
    pass

__all__ = ["correlation_fixture"]
