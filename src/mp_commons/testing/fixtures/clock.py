"""Testing fixtures – fake_clock."""
from __future__ import annotations

try:
    import pytest

    @pytest.fixture
    def fake_clock():
        """Pytest fixture: returns a FakeClock pinned to 2026-01-01 12:00 UTC."""
        from mp_commons.testing.fakes import FakeClock
        return FakeClock()

except ImportError:
    pass

__all__ = ["fake_clock"]
