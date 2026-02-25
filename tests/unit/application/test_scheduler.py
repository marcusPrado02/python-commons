"""Unit tests for §67 Application — Scheduled Jobs."""
from __future__ import annotations

import asyncio

import pytest

from mp_commons.application.scheduler import (
    InMemoryScheduler,
    Job,
    JobExecutedEvent,
    JobExecutionContext,
    Scheduler,
)


# ---------------------------------------------------------------------------
# Job
# ---------------------------------------------------------------------------
class TestJob:
    def test_cron_job(self):
        async def handler():
            pass

        job = Job(id="j1", name="Daily Report", handler=handler, cron="0 9 * * *")
        assert job.cron == "0 9 * * *"
        assert job.interval_seconds is None
        assert job.enabled is True

    def test_interval_job(self):
        async def handler():
            pass

        job = Job(id="j2", name="Heartbeat", handler=handler, interval_seconds=30)
        assert job.interval_seconds == 30
        assert job.cron is None

    def test_requires_cron_or_interval(self):
        async def handler():
            pass

        with pytest.raises(ValueError, match="cron.*interval|interval.*cron"):
            Job(id="j3", name="Bad", handler=handler)

    def test_cannot_have_both_cron_and_interval(self):
        async def handler():
            pass

        with pytest.raises(ValueError):
            Job(id="j4", name="Both", handler=handler, cron="* * * * *", interval_seconds=10)

    def test_disabled_by_default_false(self):
        async def handler():
            pass

        job = Job(id="x", name="x", handler=handler, interval_seconds=60)
        assert job.enabled is True


# ---------------------------------------------------------------------------
# JobExecutionContext
# ---------------------------------------------------------------------------
class TestJobExecutionContext:
    def test_run_successful_handler(self):
        async def _run():
            called = []

            async def handler():
                called.append(True)

            job = Job(id="j1", name="Test", handler=handler, interval_seconds=60)
            ctx = JobExecutionContext(job=job)
            event = await ctx.run()

            assert len(called) == 1
            assert isinstance(event, JobExecutedEvent)
            assert event.job_id == "j1"
            assert event.error is None
            assert event.success is True
            assert event.duration_ms >= 0
        asyncio.run(_run())
    def test_run_captures_exception(self):
        async def _run():
            async def handler():
                raise RuntimeError("boom")

            job = Job(id="j2", name="Fail", handler=handler, interval_seconds=10)
            ctx = JobExecutionContext(job=job)
            event = await ctx.run()

            assert event.error == "boom"
            assert event.success is False
        asyncio.run(_run())
    def test_run_accumulates_in_events_list(self):
        async def _run():
            async def handler():
                pass

            job = Job(id="j3", name="Loop", handler=handler, interval_seconds=5)
            ctx = JobExecutionContext(job=job)
            await ctx.run()
            await ctx.run()
            assert len(ctx.events) == 2
        asyncio.run(_run())
    def test_duration_measured(self):
        async def _run():
            async def handler():
                await asyncio.sleep(0.01)

            job = Job(id="j4", name="Slow", handler=handler, interval_seconds=1)
            ctx = JobExecutionContext(job=job)
            event = await ctx.run()
            assert event.duration_ms >= 10  # at least 10ms
        asyncio.run(_run())
# ---------------------------------------------------------------------------
# InMemoryScheduler
# ---------------------------------------------------------------------------
class TestInMemoryScheduler:
    def _make_job(self, job_id: str, calls: list | None = None) -> Job:
        if calls is None:
            calls = []

        async def handler():
            calls.append(job_id)

        handler._calls = calls  # type: ignore[attr-defined]
        return Job(id=job_id, name=f"Job {job_id}", handler=handler, interval_seconds=60)

    def test_add_and_list_jobs(self):
        scheduler = InMemoryScheduler()
        j1 = self._make_job("j1")
        j2 = self._make_job("j2")
        scheduler.add_job(j1)
        scheduler.add_job(j2)
        listed = scheduler.list_jobs()
        assert len(listed) == 2
        ids = {j.id for j in listed}
        assert ids == {"j1", "j2"}

    def test_remove_job(self):
        scheduler = InMemoryScheduler()
        j = self._make_job("j1")
        scheduler.add_job(j)
        scheduler.remove_job("j1")
        assert scheduler.list_jobs() == []

    def test_remove_nonexistent_job_is_noop(self):
        scheduler = InMemoryScheduler()
        scheduler.remove_job("ghost")  # must not raise

    def test_start_stop(self):
        async def _run():
            scheduler = InMemoryScheduler()
            assert not scheduler.is_running
            await scheduler.start()
            assert scheduler.is_running
            await scheduler.stop()
            assert not scheduler.is_running
        asyncio.run(_run())
    def test_trigger_fires_handler(self):
        async def _run():
            calls: list[str] = []
            scheduler = InMemoryScheduler()
            j = self._make_job("j1", calls)
            scheduler.add_job(j)
            event = await scheduler.trigger("j1")
            assert calls == ["j1"]
            assert event.job_id == "j1"
            assert event.success is True
        asyncio.run(_run())
    def test_trigger_captures_error(self):
        async def _run():
            async def bad_handler():
                raise ValueError("scheduler error")

            scheduler = InMemoryScheduler()
            job = Job(id="bad", name="Bad Job", handler=bad_handler, interval_seconds=10)
            scheduler.add_job(job)
            event = await scheduler.trigger("bad")
            assert event.error == "scheduler error"
            assert event.success is False
        asyncio.run(_run())
    def test_execution_log_accumulates(self):
        async def _run():
            calls: list = []
            scheduler = InMemoryScheduler()
            j = self._make_job("j1", calls)
            scheduler.add_job(j)
            await scheduler.trigger("j1")
            await scheduler.trigger("j1")
            assert len(scheduler.execution_log) == 2
        asyncio.run(_run())
    def test_is_protocol_compatible(self):
        scheduler = InMemoryScheduler()
        assert isinstance(scheduler, Scheduler)
