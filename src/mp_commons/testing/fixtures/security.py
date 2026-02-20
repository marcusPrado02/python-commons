"""Testing fixtures – fake_policy_engine."""
from __future__ import annotations

try:
    import pytest

    @pytest.fixture
    def fake_policy_engine():
        from mp_commons.testing.fakes import FakePolicyEngine
        return FakePolicyEngine()

except ImportError:
    pass

__all__ = ["fake_policy_engine"]
