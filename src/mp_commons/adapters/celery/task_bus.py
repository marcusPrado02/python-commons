"""Celery task-bus port, Celery implementation, and in-memory fake.

Requires ``celery>=5.3`` for :class:`CeleryTaskBus` and :class:`CeleryResultBackend`.
:class:`InMemoryTaskBus` is always available.
"""
from __future__ import annotations

import dataclasses
from enum import Enum
from typing import Any, Protocol, runtime_checkable


def _require_celery() -> Any:
    try:
        import celery as _celery  # type: ignore[import-untyped]

        return _celery
    except ImportError as exc:
        raise ImportError(
            "celery is required for CeleryTaskBus. "
            "Install it with: pip install 'celery>=5.3'"
        ) from exc


# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    STARTED = "STARTED"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    REVOKED = "REVOKED"
    RETRY = "RETRY"


@dataclasses.dataclass(frozen=True)
class TaskResult:
    task_id: str
    status: TaskStatus
    result: Any = None
    error: str | None = None


@dataclasses.dataclass(frozen=True)
class DispatchedTask:
    """Record kept in :class:`InMemoryTaskBus`."""
    task_name: str
    payload: dict[str, Any]
    queue: str
    countdown: int


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class TaskBus(Protocol):
    """Kernel port for dispatching background tasks."""

    def dispatch(
        self,
        task_name: str,
        payload: dict[str, Any],
        *,
        queue: str = "default",
        countdown: int = 0,
    ) -> str:
        """Enqueue *task_name* returning the task ID."""
        ...


# ---------------------------------------------------------------------------
# In-memory fake
# ---------------------------------------------------------------------------


class InMemoryTaskBus:
    """Test-double :class:`TaskBus` that stores dispatched tasks in memory."""

    def __init__(self) -> None:
        self._tasks: list[DispatchedTask] = []

    @property
    def dispatched(self) -> list[DispatchedTask]:
        """All tasks dispatched so far (in order)."""
        return list(self._tasks)

    def dispatch(
        self,
        task_name: str,
        payload: dict[str, Any],
        *,
        queue: str = "default",
        countdown: int = 0,
    ) -> str:
        task_id = f"memory-{len(self._tasks) + 1}"
        self._tasks.append(
            DispatchedTask(
                task_name=task_name,
                payload=payload,
                queue=queue,
                countdown=countdown,
            )
        )
        return task_id

    def clear(self) -> None:
        self._tasks.clear()


# ---------------------------------------------------------------------------
# Celery implementations
# ---------------------------------------------------------------------------


class CeleryTaskBus:
    """Production :class:`TaskBus` backed by a Celery application.

    Parameters
    ----------
    app:
        A configured :class:`celery.Celery` instance.
    """

    def __init__(self, app: Any) -> None:
        _require_celery()
        self._app = app

    def dispatch(
        self,
        task_name: str,
        payload: dict[str, Any],
        *,
        queue: str = "default",
        countdown: int = 0,
    ) -> str:
        result = self._app.send_task(
            task_name,
            kwargs=payload,
            queue=queue,
            countdown=countdown,
        )
        return result.id


class CeleryResultBackend:
    """Async result accessor for Celery tasks.

    Parameters
    ----------
    app:
        The same :class:`celery.Celery` instance used to dispatch tasks.
    """

    def __init__(self, app: Any) -> None:
        _require_celery()
        self._app = app

    async def get_result(self, task_id: str) -> TaskResult:
        """Fetch current result state for *task_id*."""
        async_result = self._app.AsyncResult(task_id)
        status = TaskStatus(async_result.status)
        result = None
        error = None
        if status == TaskStatus.SUCCESS:
            result = async_result.result
        elif status == TaskStatus.FAILURE:
            error = str(async_result.result)
        return TaskResult(task_id=task_id, status=status, result=result, error=error)

    def is_ready(self, task_id: str) -> bool:
        """Return ``True`` if the task has finished (success *or* failure)."""
        return self._app.AsyncResult(task_id).ready()

    def revoke(self, task_id: str, *, terminate: bool = False) -> None:
        """Revoke a pending or running task."""
        self._app.control.revoke(task_id, terminate=terminate)


__all__ = [
    "CeleryResultBackend",
    "CeleryTaskBus",
    "DispatchedTask",
    "InMemoryTaskBus",
    "TaskBus",
    "TaskResult",
    "TaskStatus",
]
