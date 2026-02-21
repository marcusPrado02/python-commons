"""Observability – AsyncLogHandler (§20.8).

A non-blocking :class:`logging.Handler` backed by :class:`asyncio.Queue`.
Log records are placed in the queue without blocking the caller;
a background task drains the queue and forwards records to a delegate handler.
"""
from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any


class AsyncLogHandler(logging.Handler):
    """Non-blocking log handler backed by an ``asyncio.Queue``.

    Records are enqueued without blocking the calling coroutine or thread.
    A background :class:`asyncio.Task` drains the queue and delegates to
    *delegate* (default: :class:`logging.StreamHandler`).

    Typical usage::

        handler = AsyncLogHandler(maxsize=10_000)
        asyncio.ensure_future(handler.start())
        logging.getLogger().addHandler(handler)

        # When shutting down:
        await handler.stop()

    Parameters
    ----------
    delegate:
        The underlying handler that performs the actual I/O.
        Defaults to a :class:`logging.StreamHandler` writing to stderr.
    maxsize:
        Maximum queue depth.  ``0`` means unlimited (default).
    level:
        Log level filter (same as any :class:`logging.Handler`).
    """

    def __init__(
        self,
        delegate: logging.Handler | None = None,
        maxsize: int = 0,
        level: int = logging.NOTSET,
    ) -> None:
        super().__init__(level)
        self._delegate = delegate or logging.StreamHandler()
        self._maxsize = maxsize
        self._queue: asyncio.Queue[logging.LogRecord | None] = asyncio.Queue(maxsize=maxsize)
        self._task: asyncio.Task[None] | None = None
        self._started = False

    # ------------------------------------------------------------------
    # logging.Handler interface
    # ------------------------------------------------------------------

    def emit(self, record: logging.LogRecord) -> None:
        """Enqueue *record* without blocking.

        If the queue is full the record is silently dropped (avoids blocking
        the calling thread / coroutine in hot paths).
        """
        try:
            self._queue.put_nowait(record)
        except asyncio.QueueFull:
            # drop rather than block
            pass
        except RuntimeError:
            # No running event loop — fall back to synchronous emit
            self._delegate.emit(record)

    def close(self) -> None:
        """Signal the drain task to stop, then close."""
        try:
            self._queue.put_nowait(None)  # sentinel
        except Exception:  # noqa: BLE001
            pass
        super().close()

    # ------------------------------------------------------------------
    # Async lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the background drain task.

        Call once from an async context::

            await handler.start()
        """
        if self._started:
            return
        self._started = True
        self._task = asyncio.ensure_future(self._drain())

    async def stop(self, timeout: float = 5.0) -> None:
        """Flush remaining records and stop the drain task.

        Parameters
        ----------
        timeout:
            Seconds to wait for the queue to drain.
        """
        try:
            await asyncio.wait_for(self._queue.join(), timeout=timeout)
        except asyncio.TimeoutError:
            pass
        self.close()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _drain(self) -> None:
        """Background task: read records from the queue and emit them."""
        while True:
            record = await self._queue.get()
            try:
                if record is None:  # sentinel
                    break
                self._delegate.emit(record)
            finally:
                self._queue.task_done()

    # ------------------------------------------------------------------
    # Sync drain helper (useful in tests / WSGI contexts)
    # ------------------------------------------------------------------

    def drain_sync(self) -> None:
        """Drain all enqueued records synchronously (blocks until empty).

        Intended for use in tests and non-async contexts.
        """
        while not self._queue.empty():
            try:
                record = self._queue.get_nowait()
                if record is not None:
                    self._delegate.emit(record)
                self._queue.task_done()
            except asyncio.QueueEmpty:
                break


__all__ = ["AsyncLogHandler"]
