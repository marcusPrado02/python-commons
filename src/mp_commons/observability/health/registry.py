from __future__ import annotations

from dataclasses import dataclass, field

from mp_commons.observability.health.check import HealthCheck, HealthStatus

__all__ = ["HealthReport", "HealthRegistry"]


@dataclass
class HealthReport:
    results: dict[str, HealthStatus] = field(default_factory=dict)

    @property
    def overall(self) -> bool:
        return all(s.healthy for s in self.results.values())

    def to_dict(self) -> dict:
        return {
            "healthy": self.overall,
            "checks": {
                name: {
                    "healthy": s.healthy,
                    "detail": s.detail,
                    "latency_ms": round(s.latency_ms, 2),
                }
                for name, s in self.results.items()
            },
        }


class HealthRegistry:
    """Runs registered health checks and aggregates results."""

    def __init__(self) -> None:
        self._checks: list[HealthCheck] = []

    def register(self, check: HealthCheck) -> None:
        self._checks.append(check)

    async def run_all(self) -> HealthReport:
        report = HealthReport()
        for check in self._checks:
            try:
                status = await check.timed_check()
            except Exception as exc:  # noqa: BLE001
                status = HealthStatus(healthy=False, detail=f"exception: {exc}")
            report.results[check.name] = status
        return report

    async def run_liveness(self) -> HealthReport:
        """Returns a report with only non-terminal checks (all registered here)."""
        return await self.run_all()
