from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable
import uuid

__all__ = [
    "InvalidTransitionError",
    "TransitionRecord",
    "WorkflowTransition",
]


class InvalidTransitionError(Exception):
    """Raised when no valid transition is found for a trigger."""

    def __init__(self, from_state: str, trigger: str) -> None:
        super().__init__(f"No transition from '{from_state}' on trigger '{trigger}'")
        self.from_state = from_state
        self.trigger = trigger


@dataclass(frozen=True)
class WorkflowTransition:
    """Describes a possible state change."""

    from_state: str
    to_state: str
    trigger: str
    guard: Callable[[Any], Awaitable[bool]] | None = field(default=None, compare=False, hash=False)
    action: Callable[[Any], Awaitable[None]] | None = field(default=None, compare=False, hash=False)


@dataclass(frozen=True)
class TransitionRecord:
    """Immutable history entry for a completed transition."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    from_state: str = ""
    to_state: str = ""
    trigger: str = ""
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    context: Any = None
