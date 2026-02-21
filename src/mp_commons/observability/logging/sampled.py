"""Observability – SampledLogger (§20.9).

A logger wrapper that emits only 1-in-N records for high-frequency events.
Sampling rate is configurable per log level.
"""
from __future__ import annotations

import threading
from collections import defaultdict
from typing import Any


class SampledLogger:
    """Wraps any logger, emitting only 1-in-N records per log level.

    Useful for suppressing noise from high-frequency events (e.g. health
    probes, cache hits) without losing the signal entirely.

    Parameters
    ----------
    logger:
        The underlying logger to delegate to when a sample is taken.
    sample_rates:
        A mapping of log level name → emit-1-in-N.
        Example: ``{"DEBUG": 100, "INFO": 10}`` emits 1 % of DEBUG calls
        and 10 % of INFO calls.  Levels not specified are always emitted.
    default_rate:
        Fallback rate for levels not listed in *sample_rates*.
        ``1`` means always emit (default).

    Example
    -------
    ::

        import structlog
        from mp_commons.observability.logging.sampled import SampledLogger

        base = structlog.get_logger("my_service")
        log = SampledLogger(base, sample_rates={"DEBUG": 100, "INFO": 10})
        log.debug("cache_hit", key="abc")   # emits 1 % of the time
        log.info("request_received")        # emits 10 % of the time
        log.error("unhandled_exception")    # always emitted
    """

    def __init__(
        self,
        logger: Any,
        sample_rates: dict[str, int] | None = None,
        default_rate: int = 1,
    ) -> None:
        self._logger = logger
        self._rates: dict[str, int] = {k.upper(): v for k, v in (sample_rates or {}).items()}
        self._default_rate = max(1, default_rate)
        self._counters: dict[str, int] = defaultdict(int)
        self._lock = threading.Lock()

    def _should_emit(self, level: str) -> bool:
        rate = self._rates.get(level.upper(), self._default_rate)
        if rate <= 1:
            return True
        with self._lock:
            self._counters[level] += 1
            return self._counters[level] % rate == 1

    def _delegate(self, level: str, event: str, **kwargs: Any) -> None:
        if self._should_emit(level):
            method = getattr(self._logger, level.lower(), None)
            if method is not None:
                method(event, **kwargs)

    def debug(self, event: str, **kwargs: Any) -> None:
        self._delegate("debug", event, **kwargs)

    def info(self, event: str, **kwargs: Any) -> None:
        self._delegate("info", event, **kwargs)

    def warning(self, event: str, **kwargs: Any) -> None:
        self._delegate("warning", event, **kwargs)

    # common alias
    warn = warning

    def error(self, event: str, **kwargs: Any) -> None:
        self._delegate("error", event, **kwargs)

    def critical(self, event: str, **kwargs: Any) -> None:
        self._delegate("critical", event, **kwargs)

    def bind(self, **kwargs: Any) -> "SampledLogger":
        """Return a new :class:`SampledLogger` with bound context."""
        try:
            bound_logger = self._logger.bind(**kwargs)
        except AttributeError:
            bound_logger = self._logger
        return SampledLogger(
            bound_logger,
            sample_rates={k: v for k, v in self._rates.items()},
            default_rate=self._default_rate,
        )

    def reset_counters(self) -> None:
        """Reset sampling counters (useful in tests)."""
        with self._lock:
            self._counters.clear()


__all__ = ["SampledLogger"]
