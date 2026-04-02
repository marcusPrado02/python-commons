"""Resilience – Graceful shutdown helper.

:class:`GracefulShutdown` intercepts ``SIGTERM`` / ``SIGINT`` and gives the
application a chance to finish in-flight work before exiting.

Usage::

    shutdown = GracefulShutdown(drain_timeout=30.0)


    @shutdown.on_shutdown
    async def close_db():
        await pool.close()


    @shutdown.on_shutdown
    async def flush_metrics():
        await registry.flush()


    # In your main coroutine:
    shutdown.install()  # register signal handlers
    await shutdown.wait()  # blocks until SIGTERM / SIGINT
    # hooks are called automatically in LIFO order after wait() returns
    # OR call explicitly:
    await shutdown.run_hooks()

Shutdown hooks are called in **LIFO** order (last registered, first called),
mirroring Python's :mod:`atexit` behaviour.  Both sync and async callables
are accepted.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import logging
import signal
from typing import Any

logger = logging.getLogger(__name__)


class GracefulShutdown:
    """Coordinate a graceful application shutdown on ``SIGTERM`` / ``SIGINT``.

    Parameters
    ----------
    drain_timeout:
        Seconds to wait for all registered hooks to complete.  Hooks that
        exceed this budget are cancelled and a warning is logged.  Default
        is ``30.0`` seconds.
    signals:
        OS signals that trigger shutdown.  Defaults to
        ``(signal.SIGTERM, signal.SIGINT)``.
    """

    def __init__(
        self,
        drain_timeout: float = 30.0,
        signals: tuple[signal.Signals, ...] | None = None,
    ) -> None:
        self._drain_timeout = drain_timeout
        self._signals = signals or (signal.SIGTERM, signal.SIGINT)
        self._hooks: list[Callable[[], Any]] = []
        self._event = asyncio.Event()
        self._triggered_by: signal.Signals | None = None

    # ------------------------------------------------------------------
    # Hook registration
    # ------------------------------------------------------------------

    def on_shutdown(self, func: Callable[[], Any]) -> Callable[[], Any]:
        """Decorator / callable that registers *func* as a shutdown hook.

        Hooks are called in **LIFO** order (last registered, first called).

        Parameters
        ----------
        func:
            A sync or async callable that takes no arguments.
        """
        self._hooks.append(func)
        return func

    def register(self, func: Callable[[], Any]) -> None:
        """Register *func* as a shutdown hook (non-decorator form)."""
        self._hooks.append(func)

    # ------------------------------------------------------------------
    # Signal handling
    # ------------------------------------------------------------------

    def install(self) -> None:
        """Attach signal handlers to the running event loop.

        Must be called from within a running asyncio event loop::

            loop = asyncio.get_event_loop()
            loop.run_until_complete(main())

        Or, inside an async function::

            shutdown.install()
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.get_event_loop()

        for sig in self._signals:
            try:
                loop.add_signal_handler(sig, self._handle_signal, sig)
            except (ValueError, NotImplementedError):
                # NotImplementedError on Windows; ValueError for invalid signals
                logger.warning("Cannot install signal handler for %s", sig)

    def _handle_signal(self, sig: signal.Signals) -> None:
        if not self._event.is_set():
            logger.info("Received signal %s — initiating graceful shutdown", sig.name)
            self._triggered_by = sig
            self._event.set()

    # ------------------------------------------------------------------
    # Main wait / run hooks
    # ------------------------------------------------------------------

    async def wait(self) -> None:
        """Block until a shutdown signal is received, then run all hooks.

        This is the primary entry point for the main coroutine::

            shutdown.install()
            await shutdown.wait()
            # application exits cleanly
        """
        await self._event.wait()
        await self.run_hooks()

    async def run_hooks(self) -> None:
        """Call all registered hooks in LIFO order within *drain_timeout*.

        Each hook is called sequentially.  If the total time exceeds
        *drain_timeout*, remaining hooks are skipped and a warning is logged.
        """
        hooks = list(reversed(self._hooks))
        if not hooks:
            return

        logger.info("Running %d shutdown hook(s) (timeout=%.1fs)", len(hooks), self._drain_timeout)
        deadline = asyncio.get_event_loop().time() + self._drain_timeout

        for hook in hooks:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                logger.warning("Drain timeout exceeded — skipping remaining shutdown hooks")
                break
            name = getattr(hook, "__name__", repr(hook))
            try:
                result = hook()
                if asyncio.iscoroutine(result):
                    await asyncio.wait_for(result, timeout=remaining)
                logger.debug("Shutdown hook %r completed", name)
            except TimeoutError:
                logger.warning("Shutdown hook %r timed out", name)
            except Exception:
                logger.exception("Shutdown hook %r raised an exception", name)

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def is_shutting_down(self) -> bool:
        """``True`` once a shutdown signal has been received."""
        return self._event.is_set()

    @property
    def triggered_by(self) -> signal.Signals | None:
        """The signal that triggered shutdown, or ``None`` if not yet triggered."""
        return self._triggered_by

    @property
    def hook_count(self) -> int:
        """Number of registered shutdown hooks."""
        return len(self._hooks)

    def trigger(self) -> None:
        """Programmatically trigger shutdown (useful for testing)."""
        if not self._event.is_set():
            self._event.set()


__all__ = ["GracefulShutdown"]
