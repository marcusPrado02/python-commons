from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

__all__ = [
    "BurnRateAlert",
    "ErrorBudget",
    "InMemorySLOTracker",
    "SLOAlertEvent",
    "SLODefinition",
    "SLOTracker",
]


@dataclass(frozen=True)
class SLODefinition:
    name: str
    target: float         # 0.0–1.0, e.g. 0.999 for 99.9 %
    window_days: int = 30
    metric_name: str = ""


@dataclass
class ErrorBudget:
    slo: SLODefinition
    total_requests: int
    error_count: int

    def allowed_errors(self) -> float:
        return self.total_requests * (1.0 - self.slo.target)

    def remaining_budget(self) -> float:
        """Fraction of error budget remaining (1.0 = full, 0.0 = exhausted)."""
        allowed = self.allowed_errors()
        if allowed <= 0:
            return 0.0
        remaining = max(0.0, allowed - self.error_count)
        return remaining / allowed

    def burn_rate(self, window_hours: float = 1.0) -> float:
        """Approx burn rate relative to a proportional sub-window."""
        if self.total_requests == 0 or window_hours <= 0:
            return 0.0
        error_rate = self.error_count / self.total_requests
        ideal_error_rate = 1.0 - self.slo.target
        if ideal_error_rate == 0:
            return float("inf")
        return error_rate / ideal_error_rate

    def is_exhausted(self) -> bool:
        return self.error_count >= self.allowed_errors()


@dataclass(frozen=True)
class SLOAlertEvent:
    slo_name: str
    burn_rate: float
    threshold: float
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class InMemorySLOTracker:
    """Simple in-memory SLO tracker; accumulates request/error counts per metric."""

    def __init__(self) -> None:
        self._totals: dict[str, int] = {}
        self._errors: dict[str, int] = {}
        self.events: list[SLOAlertEvent] = []

    async def record_request(self, metric_name: str, success: bool) -> None:
        self._totals[metric_name] = self._totals.get(metric_name, 0) + 1
        if not success:
            self._errors[metric_name] = self._errors.get(metric_name, 0) + 1

    async def get_budget(self, slo: SLODefinition) -> ErrorBudget:
        total = self._totals.get(slo.metric_name, 0)
        errors = self._errors.get(slo.metric_name, 0)
        return ErrorBudget(slo=slo, total_requests=total, error_count=errors)


class BurnRateAlert:
    """Emits SLOAlertEvent via callback when burn rate exceeds threshold."""

    def __init__(
        self,
        tracker: InMemorySLOTracker,
        threshold: float = 14.4,
        on_alert: Callable[[SLOAlertEvent], Awaitable[None]] | None = None,
    ) -> None:
        self._tracker = tracker
        self._threshold = threshold
        self._on_alert = on_alert

    async def check(self, slo: SLODefinition) -> bool:
        budget = await self._tracker.get_budget(slo)
        rate = budget.burn_rate()
        if rate >= self._threshold:
            evt = SLOAlertEvent(slo_name=slo.name, burn_rate=rate, threshold=self._threshold)
            self._tracker.events.append(evt)
            if self._on_alert:
                await self._on_alert(evt)
            return True
        return False


# Backwards-compat alias
SLOTracker = InMemorySLOTracker
