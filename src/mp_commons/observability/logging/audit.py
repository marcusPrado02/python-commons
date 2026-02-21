"""Observability – AuditLogger (§20.7).

A dedicated structured-log sink for security-sensitive actions.
"""
from __future__ import annotations

import datetime
import logging
from enum import Enum
from typing import Any


class AuditOutcome(str, Enum):
    """Standardised audit outcomes."""

    SUCCESS = "success"
    FAILURE = "failure"
    DENIED = "denied"
    ERROR = "error"


class AuditLogger:
    """Dedicated structured-log sink for security-sensitive actions.

    All audit entries are emitted at ``WARNING`` level so they pass through
    even restrictive log-level filters.

    Parameters
    ----------
    service:
        Logical service name injected into every audit entry.
    logger:
        Underlying logger to use.  Defaults to a Python :mod:`logging`
        logger named ``audit``.  Pass a structlog logger for JSON output.
    """

    def __init__(
        self,
        service: str = "unknown",
        logger: Any = None,
    ) -> None:
        self._service = service
        if logger is None:
            self._log = logging.getLogger("audit")
        else:
            self._log = logger

    def log_access(
        self,
        principal: Any,
        resource: str,
        action: str,
        outcome: AuditOutcome | str = AuditOutcome.SUCCESS,
        **extra: Any,
    ) -> None:
        """Record a security access event.

        Parameters
        ----------
        principal:
            The user or service performing the action.  Uses
            ``principal.id`` if available, otherwise ``str(principal)``.
        resource:
            The resource being accessed (e.g. ``"document:42"``).
        action:
            The action performed (e.g. ``"read"``, ``"delete"``).
        outcome:
            :class:`AuditOutcome` or plain string (``"success"`` / ``"failure"``).
        **extra:
            Additional structured fields to include in the audit entry.
        """
        principal_id = getattr(principal, "id", None) or str(principal)
        entry: dict[str, Any] = {
            "event": "audit.access",
            "service": self._service,
            "principal_id": principal_id,
            "resource": resource,
            "action": action,
            "outcome": outcome.value if isinstance(outcome, AuditOutcome) else str(outcome),
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            **extra,
        }
        self._emit(entry)

    def log_security_event(
        self,
        event_type: str,
        principal: Any = None,
        description: str = "",
        **extra: Any,
    ) -> None:
        """Record a generic security event (login attempt, token refresh, …).

        Parameters
        ----------
        event_type:
            Short identifier such as ``"login"``, ``"logout"``,
            ``"token_refresh"``, ``"password_change"``.
        principal:
            Optional actor performing the event.
        description:
            Human-readable description of what happened.
        **extra:
            Additional structured fields.
        """
        principal_id: str | None = None
        if principal is not None:
            principal_id = getattr(principal, "id", None) or str(principal)

        entry: dict[str, Any] = {
            "event": f"audit.{event_type}",
            "service": self._service,
            "event_type": event_type,
            "description": description,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            **extra,
        }
        if principal_id is not None:
            entry["principal_id"] = principal_id
        self._emit(entry)

    def _emit(self, entry: dict[str, Any]) -> None:
        # structlog bound loggers accept event as first positional arg
        try:
            import structlog  # noqa: F401  - just check it exists
            event = entry.pop("event", "audit")
            self._log.warning(event, **entry)
        except (ImportError, TypeError):
            # stdlib logger: format as key=value pairs
            event = entry.pop("event", "audit")
            msg = " ".join(f"{k}={v!r}" for k, v in entry.items())
            self._log.warning("%s %s", event, msg)


__all__ = ["AuditLogger", "AuditOutcome"]
