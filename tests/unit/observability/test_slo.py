"""Unit tests for §81 – Observability SLO / Error Budget."""
import asyncio

import pytest

from mp_commons.observability.slo import (
    BurnRateAlert,
    ErrorBudget,
    InMemorySLOTracker,
    SLOAlertEvent,
    SLODefinition,
)


def _slo(target: float = 0.99, metric: str = "api") -> SLODefinition:
    return SLODefinition(name="api_slo", target=target, window_days=30, metric_name=metric)


class TestErrorBudget:
    def test_full_budget_when_no_errors(self):
        slo = _slo(0.99)
        budget = ErrorBudget(slo=slo, total_requests=1000, error_count=0)
        assert budget.remaining_budget() == pytest.approx(1.0)

    def test_zero_budget_when_exhausted(self):
        slo = _slo(0.99)
        budget = ErrorBudget(slo=slo, total_requests=1000, error_count=10)
        assert budget.remaining_budget() == pytest.approx(0.0)

    def test_partial_budget(self):
        slo = _slo(0.99)
        budget = ErrorBudget(slo=slo, total_requests=1000, error_count=5)
        assert 0.0 < budget.remaining_budget() < 1.0

    def test_is_exhausted_true(self):
        slo = _slo(0.99)
        budget = ErrorBudget(slo=slo, total_requests=1000, error_count=11)
        assert budget.is_exhausted() is True

    def test_is_exhausted_false(self):
        slo = _slo(0.99)
        budget = ErrorBudget(slo=slo, total_requests=1000, error_count=5)
        assert budget.is_exhausted() is False

    def test_burn_rate_one_on_perfect_error_rate(self):
        """If actual error rate equals SLO budget rate, burn rate = 1."""
        slo = _slo(0.99)
        budget = ErrorBudget(slo=slo, total_requests=1000, error_count=10)
        assert budget.burn_rate() == pytest.approx(1.0)

    def test_burn_rate_zero_on_no_errors(self):
        slo = _slo(0.99)
        budget = ErrorBudget(slo=slo, total_requests=1000, error_count=0)
        assert budget.burn_rate() == pytest.approx(0.0)

    def test_burn_rate_zero_when_no_requests(self):
        slo = _slo(0.99)
        budget = ErrorBudget(slo=slo, total_requests=0, error_count=0)
        assert budget.burn_rate() == 0.0


class TestInMemorySLOTracker:
    def test_record_and_get_budget(self):
        tracker = InMemorySLOTracker()
        slo = _slo(0.99, "api")
        for _ in range(900):
            asyncio.run(tracker.record_request("api", success=True))
        for _ in range(100):
            asyncio.run(tracker.record_request("api", success=False))
        budget = asyncio.run(tracker.get_budget(slo))
        assert budget.total_requests == 1000
        assert budget.error_count == 100

    def test_no_requests_gives_empty_budget(self):
        tracker = InMemorySLOTracker()
        slo = _slo(metric="unknown")
        budget = asyncio.run(tracker.get_budget(slo))
        assert budget.total_requests == 0


class TestBurnRateAlert:
    def test_alert_fires_above_threshold(self):
        tracker = InMemorySLOTracker()
        slo = _slo(0.99, "api")
        alerts = []

        async def on_alert(evt: SLOAlertEvent):
            alerts.append(evt)

        alert = BurnRateAlert(tracker, threshold=14.4, on_alert=on_alert)
        # 100% errors → burn rate = 100
        for _ in range(100):
            asyncio.run(tracker.record_request("api", success=False))
        fired = asyncio.run(alert.check(slo))
        assert fired is True
        assert len(alerts) == 1
        assert alerts[0].slo_name == "api_slo"

    def test_alert_does_not_fire_below_threshold(self):
        tracker = InMemorySLOTracker()
        slo = _slo(0.99, "api")
        alert = BurnRateAlert(tracker, threshold=14.4)
        # All success
        for _ in range(1000):
            asyncio.run(tracker.record_request("api", success=True))
        fired = asyncio.run(alert.check(slo))
        assert fired is False
