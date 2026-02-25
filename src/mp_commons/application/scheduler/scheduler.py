"""Application scheduler – Scheduler Protocol and JobExecutionContext."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol, runtime_checkable

from mp_commons.application.scheduler.job import Job

__all__ = ["JobExecutedEvent", "JobExecutionContext", "Scheduler"]


@dataclass(frozen=True)
class JobExecutedEvent:
    """Event emitted after a job completes (successfully or not)."""

    job_id: str
    job_name: str
    started_at: datetime
    duration_ms: float
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.error is None


@dataclass
class JobExecutionContext:
    """Run a job handler and capture execution details."""

    job: Job
    events: list[JobExecutedEvent] = field(default_factory=list)

    async def run(self) -> JobExecutedEvent:
        started_at = datetime.now(tz=timezone.utc)
        t0 = time.monotonic()
        error: str | None = None
        try:
            await self.job.handler()
        except Exception as exc:  # noqa: BLE001
            error = str(exc)
        duration_ms = (time.monotonic() - t0) * 1000
        event = JobExecutedEvent(
            job_id=self.job.id,
            job_name=self.job.name,
            started_at=started_at,
            duration_ms=duration_ms,
            error=error,
        )
        self.events.append(event)
        return event


@runtime_checkable
class Scheduler(Protocol):
    """Port: manage and run scheduled jobs."""

    def add_job(self, job: Job) -> None: ...
    def remove_job(self, job_id: str) -> None: ...
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    def list_jobs(self) -> list[Job]: ...
