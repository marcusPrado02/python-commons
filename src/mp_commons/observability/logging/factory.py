"""Observability – JsonLoggerFactory."""
from __future__ import annotations

import logging
from typing import Any

from mp_commons.observability.logging.filters import SensitiveFieldsFilter


class JsonLoggerFactory:
    """Configure structlog for JSON output (if structlog is installed)."""

    @staticmethod
    def configure(level: int = logging.INFO, sensitive_fields: frozenset[str] | None = None) -> None:
        try:
            import structlog

            shared_processors: list[Any] = [
                structlog.contextvars.merge_contextvars,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
            ]
            if sensitive_fields:
                _filter = SensitiveFieldsFilter(sensitive_fields)

                def _redact(logger: Any, method: Any, event_dict: dict[str, Any]) -> dict[str, Any]:  # noqa: ARG001
                    return _filter.redact_deep(event_dict)

                shared_processors.insert(0, _redact)

            structlog.configure(
                processors=shared_processors + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
                logger_factory=structlog.stdlib.LoggerFactory(),
                wrapper_class=structlog.stdlib.BoundLogger,
                cache_logger_on_first_use=True,
            )
            formatter = structlog.stdlib.ProcessorFormatter(
                processors=[
                    structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                    structlog.processors.JSONRenderer(),
                ],
            )
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            root = logging.getLogger()
            root.handlers.clear()
            root.addHandler(handler)
            root.setLevel(level)

        except ImportError:
            logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s %(message)s")


__all__ = ["JsonLoggerFactory"]
