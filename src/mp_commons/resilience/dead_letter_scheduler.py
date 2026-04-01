"""DeadLetterReplayScheduler — periodic job for replaying dead-lettered messages (R-04).

Periodically queries the :class:`~mp_commons.kernel.messaging.DeadLetterStore`
for unreplayed entries and re-enqueues them for processing.  An exponential
backoff ensures entries that keep failing are not replayed too aggressively.

Usage::

    from mp_commons.resilience.dead_letter_scheduler import DeadLetterReplayScheduler

    scheduler = DeadLetterReplayScheduler(
        store=my_dead_letter_store,
        interval_seconds=60.0,
        max_retries=3,
        backoff_base=2.0,
    )

    # Integrate with GracefulShutdown:
    async def run():
        shutdown = GracefulShutdown()
        shutdown.on_shutdown(scheduler.stop)
        shutdown.install()
        await scheduler.start()
        await shutdown.wait()
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from mp_commons.kernel.messaging.dead_letter import DeadLetterEntry, DeadLetterStore

logger = logging.getLogger(__name__)


class DeadLetterReplayScheduler:
    """Periodically replays dead-lettered messages via :class:`DeadLetterStore`.

    Parameters
    ----------
    store:
        The dead-letter store implementation to query and replay from.
    interval_seconds:
        How often (in seconds) to poll for unreplayed entries.
    max_retries:
        Maximum replay attempts per entry before marking it as permanently failed.
        An entry's ``retry_count`` is used to determine the backoff.
    backoff_base:
        Base for exponential backoff between retries.  The wait before attempt
        *n* is ``min(backoff_base ** n, max_backoff_seconds)`` seconds.
    max_backoff_seconds:
        Cap on per-entry backoff to prevent excessively long waits.
    batch_size:
        Number of entries to replay per poll cycle.
    """

    def __init__(
        self,
        store: DeadLetterStore,
        interval_seconds: float = 60.0,
        max_retries: int = 5,
        backoff_base: float = 2.0,
        max_backoff_seconds: float = 3600.0,
        batch_size: int = 50,
    ) -> None:
        if interval_seconds <= 0:
            raise ValueError(f"interval_seconds must be positive, got {interval_seconds}")
        if max_retries < 0:
            raise ValueError(f"max_retries must be ≥ 0, got {max_retries}")

        self._store = store
        self._interval = interval_seconds
        self._max_retries = max_retries
        self._backoff_base = backoff_base
        self._max_backoff = max_backoff_seconds
        self._batch_size = batch_size
        self._running = False
        self._task: asyncio.Task[None] | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the background replay loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop(), name="dead_letter_replay")
        logger.info(
            "dead_letter_scheduler.started interval_seconds=%.1f max_retries=%d",
            self._interval, self._max_retries,
        )

    async def stop(self) -> None:
        """Stop the replay loop gracefully."""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("dead_letter_scheduler.stopped")

    async def run_once(self) -> int:
        """Run one replay cycle; returns the number of entries replayed.

        Useful for testing or manual trigger without starting the loop.
        """
        return await self._replay_batch()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _loop(self) -> None:
        while self._running:
            try:
                replayed = await self._replay_batch()
                if replayed:
                    logger.info("dead_letter_scheduler.cycle replayed=%d", replayed)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("dead_letter_scheduler.cycle_error")
            try:
                await asyncio.sleep(self._interval)
            except asyncio.CancelledError:
                break

    async def _replay_batch(self) -> int:
        entries: list[DeadLetterEntry] = await self._store.list(limit=self._batch_size)
        replayed = 0
        for entry in entries:
            if entry.replayed:
                continue
            if entry.retry_count >= self._max_retries:
                logger.warning(
                    "dead_letter_scheduler.giving_up entry_id=%s retry_count=%d",
                    entry.id, entry.retry_count,
                )
                continue
            backoff = min(
                self._backoff_base ** entry.retry_count,
                self._max_backoff,
            )
            if backoff > 0:
                await asyncio.sleep(backoff)
            try:
                await self._store.replay(entry.id)
                replayed += 1
                logger.debug("dead_letter_scheduler.replayed entry_id=%s", entry.id)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception(
                    "dead_letter_scheduler.replay_failed entry_id=%s", entry.id
                )
        return replayed


__all__ = ["DeadLetterReplayScheduler"]
