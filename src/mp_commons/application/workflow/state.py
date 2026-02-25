from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

__all__ = ["WorkflowState"]


@dataclass(frozen=True)
class WorkflowState:
    """A named state in a workflow definition."""

    name: str
    is_initial: bool = False
    is_terminal: bool = False
    on_enter: Callable[[str, Any], Awaitable[None]] | None = field(default=None, compare=False, hash=False)
    on_exit: Callable[[str, Any], Awaitable[None]] | None = field(default=None, compare=False, hash=False)
