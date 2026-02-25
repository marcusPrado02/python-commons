"""Application scheduler – InMemoryScheduler for unit tests."""
from __future__ import annotations

from mp_commons.application.scheduler.job import Job
from mp_commons.application.scheduler.scheduler import JobExecutionContext, JobExecutedEvent

__all__ = ["InMemoryScheduler"]


class InMemoryScheduler:
    """Scheduler that stores jobs in memory; ``trigger`` fires a job manually."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._running: bool = False
        self.execution_log: list[JobExecutedEvent] = []

    def add_job(self, job: Job) -> None:
        self._jobs[job.id] = job

    def remove_job(self, job_id: str) -> None:
        self._jobs.pop(job_id, None)

    async def start(self) -> None:
        self._running = True

    async def stop(self) -> None:
        self._running = False

    def list_jobs(self) -> list[Job]:
        return list(self._jobs.values())

    async def trigger(self, job_id: str) -> JobExecutedEvent:
        """Manually fire a job's handler and record the result."""
        job = self._jobs[job_id]
        ctx = JobExecutionContext(job=job)
        event = await ctx.run()
        self.execution_log.append(event)
        return event

    @property
    def is_running(self) -> bool:
        return self._running
