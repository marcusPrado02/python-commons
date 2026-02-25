"""Application scheduler – APSchedulerAdapter (requires apscheduler>=4 extra)."""
from __future__ import annotations

from typing import Any

from mp_commons.application.scheduler.job import Job
from mp_commons.application.scheduler.scheduler import JobExecutionContext

__all__ = ["APSchedulerAdapter"]


def _require_apscheduler() -> Any:  # pragma: no cover
    try:
        import apscheduler  # noqa: PLC0415
        return apscheduler
    except ImportError as exc:
        raise ImportError(
            "APScheduler>=4.0 is required. "
            "Install it with: pip install 'apscheduler>=4'"
        ) from exc


class APSchedulerAdapter:
    """Scheduler backed by APScheduler >= 4.0."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._scheduler: Any | None = None

    def _get_scheduler(self) -> Any:  # pragma: no cover
        if self._scheduler is None:
            apscheduler = _require_apscheduler()
            from apscheduler.schedulers.async_ import AsyncScheduler  # noqa: PLC0415
            self._scheduler = AsyncScheduler()
        return self._scheduler

    def add_job(self, job: Job) -> None:
        self._jobs[job.id] = job

    def remove_job(self, job_id: str) -> None:
        self._jobs.pop(job_id, None)

    async def start(self) -> None:  # pragma: no cover
        scheduler = self._get_scheduler()
        for job in self._jobs.values():
            await self._register_job(scheduler, job)
        await scheduler.start_in_background()

    async def _register_job(self, scheduler: Any, job: Job) -> None:  # pragma: no cover
        from apscheduler.triggers.cron import CronTrigger  # noqa: PLC0415
        from apscheduler.triggers.interval import IntervalTrigger  # noqa: PLC0415

        async def _handler() -> None:
            ctx = JobExecutionContext(job=job)
            await ctx.run()

        if job.cron:
            trigger = CronTrigger.from_crontab(job.cron)
        else:
            from datetime import timedelta  # noqa: PLC0415
            trigger = IntervalTrigger(seconds=job.interval_seconds)

        await scheduler.add_schedule(_handler, trigger=trigger, id=job.id)

    async def stop(self) -> None:  # pragma: no cover
        if self._scheduler:
            await self._scheduler.stop()

    def list_jobs(self) -> list[Job]:
        return list(self._jobs.values())
