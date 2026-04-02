"""Unit tests for DeadLetterReplayScheduler (R-04)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from mp_commons.resilience.dead_letter_scheduler import DeadLetterReplayScheduler

# ---------------------------------------------------------------------------
# Minimal in-memory DeadLetterStore stub
# ---------------------------------------------------------------------------


@dataclass
class FakeEntry:
    id: str
    retry_count: int = 0
    replayed: bool = False
    payload: Any = None


class FakeDeadLetterStore:
    def __init__(self, entries: list[FakeEntry] | None = None) -> None:
        self.entries: list[FakeEntry] = list(entries or [])
        self.replayed_ids: list[str] = []
        self.fail_ids: set[str] = set()

    async def list(self, limit: int = 50) -> list[FakeEntry]:
        return self.entries[:limit]

    async def replay(self, entry_id: str) -> None:
        if entry_id in self.fail_ids:
            raise RuntimeError(f"replay failed: {entry_id}")
        for e in self.entries:
            if e.id == entry_id:
                e.replayed = True
                self.replayed_ids.append(entry_id)
                return
        raise KeyError(entry_id)


# ---------------------------------------------------------------------------
# Constructor validation
# ---------------------------------------------------------------------------


class TestConstructorValidation:
    def test_negative_interval_raises(self):
        with pytest.raises(ValueError, match="interval_seconds"):
            DeadLetterReplayScheduler(store=FakeDeadLetterStore(), interval_seconds=-1.0)

    def test_zero_interval_raises(self):
        with pytest.raises(ValueError, match="interval_seconds"):
            DeadLetterReplayScheduler(store=FakeDeadLetterStore(), interval_seconds=0.0)

    def test_negative_max_retries_raises(self):
        with pytest.raises(ValueError, match="max_retries"):
            DeadLetterReplayScheduler(store=FakeDeadLetterStore(), max_retries=-1)

    def test_zero_max_retries_is_valid(self):
        # max_retries=0 means give up immediately; should not raise
        s = DeadLetterReplayScheduler(store=FakeDeadLetterStore(), max_retries=0)
        assert s is not None


# ---------------------------------------------------------------------------
# run_once — basic replaying
# ---------------------------------------------------------------------------


class TestRunOnce:
    @pytest.mark.asyncio
    async def test_replays_single_entry(self):
        store = FakeDeadLetterStore([FakeEntry("e1")])
        with patch("asyncio.sleep", new_callable=AsyncMock):
            s = DeadLetterReplayScheduler(store=store)
            count = await s.run_once()
        assert count == 1
        assert store.replayed_ids == ["e1"]

    @pytest.mark.asyncio
    async def test_skips_already_replayed(self):
        store = FakeDeadLetterStore([FakeEntry("e1", replayed=True)])
        s = DeadLetterReplayScheduler(store=store)
        count = await s.run_once()
        assert count == 0
        assert store.replayed_ids == []

    @pytest.mark.asyncio
    async def test_skips_exhausted_entries(self):
        store = FakeDeadLetterStore([FakeEntry("e1", retry_count=5)])
        s = DeadLetterReplayScheduler(store=store, max_retries=5)
        count = await s.run_once()
        assert count == 0

    @pytest.mark.asyncio
    async def test_replays_multiple_entries(self):
        entries = [FakeEntry(f"e{i}") for i in range(3)]
        store = FakeDeadLetterStore(entries)
        with patch("asyncio.sleep", new_callable=AsyncMock):
            s = DeadLetterReplayScheduler(store=store)
            count = await s.run_once()
        assert count == 3
        assert set(store.replayed_ids) == {"e0", "e1", "e2"}

    @pytest.mark.asyncio
    async def test_handles_replay_failure_gracefully(self):
        store = FakeDeadLetterStore([FakeEntry("e1"), FakeEntry("e2")])
        store.fail_ids.add("e1")
        with patch("asyncio.sleep", new_callable=AsyncMock):
            s = DeadLetterReplayScheduler(store=store)
            count = await s.run_once()
        # e1 failed, e2 succeeded → count=1
        assert count == 1
        assert store.replayed_ids == ["e2"]

    @pytest.mark.asyncio
    async def test_returns_zero_for_empty_store(self):
        store = FakeDeadLetterStore([])
        s = DeadLetterReplayScheduler(store=store)
        count = await s.run_once()
        assert count == 0


# ---------------------------------------------------------------------------
# Backoff behaviour
# ---------------------------------------------------------------------------


class TestBackoffBehaviour:
    @pytest.mark.asyncio
    async def test_backoff_increases_with_retry_count(self):
        sleep_calls: list[float] = []

        async def record_sleep(delay: float) -> None:
            sleep_calls.append(delay)

        entries = [FakeEntry("e0", retry_count=0), FakeEntry("e1", retry_count=2)]
        store = FakeDeadLetterStore(entries)
        with patch("asyncio.sleep", side_effect=record_sleep):
            s = DeadLetterReplayScheduler(store=store, backoff_base=2.0)
            await s.run_once()

        # retry_count=0 → backoff = 2^0 = 1.0; retry_count=2 → backoff = 2^2 = 4.0
        assert sleep_calls[0] == pytest.approx(1.0)
        assert sleep_calls[1] == pytest.approx(4.0)

    @pytest.mark.asyncio
    async def test_backoff_capped_by_max(self):
        sleep_calls: list[float] = []

        async def record_sleep(delay: float) -> None:
            sleep_calls.append(delay)

        entries = [FakeEntry("big", retry_count=10)]
        store = FakeDeadLetterStore(entries)
        with patch("asyncio.sleep", side_effect=record_sleep):
            s = DeadLetterReplayScheduler(
                store=store,
                backoff_base=2.0,
                max_backoff_seconds=30.0,
                max_retries=20,
            )
            await s.run_once()

        assert sleep_calls[0] == pytest.approx(30.0)


# ---------------------------------------------------------------------------
# Lifecycle — start / stop
# ---------------------------------------------------------------------------


class TestLifecycle:
    @pytest.mark.asyncio
    async def test_start_creates_background_task(self):
        store = FakeDeadLetterStore([])
        s = DeadLetterReplayScheduler(store=store, interval_seconds=9999.0)
        await s.start()
        assert s._task is not None
        assert not s._task.done()
        await s.stop()

    @pytest.mark.asyncio
    async def test_double_start_is_idempotent(self):
        store = FakeDeadLetterStore([])
        s = DeadLetterReplayScheduler(store=store, interval_seconds=9999.0)
        await s.start()
        task1 = s._task
        await s.start()  # second call should be no-op
        assert s._task is task1
        await s.stop()

    @pytest.mark.asyncio
    async def test_stop_cancels_task(self):
        store = FakeDeadLetterStore([])
        s = DeadLetterReplayScheduler(store=store, interval_seconds=9999.0)
        await s.start()
        await s.stop()
        assert s._task is None

    @pytest.mark.asyncio
    async def test_stop_without_start_is_safe(self):
        store = FakeDeadLetterStore([])
        s = DeadLetterReplayScheduler(store=store)
        await s.stop()  # must not raise

    @pytest.mark.asyncio
    async def test_batch_size_limits_entries_fetched(self):
        entries = [FakeEntry(f"e{i}") for i in range(10)]
        store = FakeDeadLetterStore(entries)
        with patch("asyncio.sleep", new_callable=AsyncMock):
            s = DeadLetterReplayScheduler(store=store, batch_size=3)
            count = await s.run_once()
        assert count == 3
