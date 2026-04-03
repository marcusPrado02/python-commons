"""Unit tests for the Celery task-bus adapter (§50)."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

from mp_commons.adapters.celery.task_bus import (
    CeleryResultBackend,
    CeleryTaskBus,
    InMemoryTaskBus,
    TaskStatus,
)

# ---------------------------------------------------------------------------
# InMemoryTaskBus
# ---------------------------------------------------------------------------


def test_in_memory_dispatch_returns_id():
    bus = InMemoryTaskBus()
    task_id = bus.dispatch("my.task", {"key": "val"}, queue="high", countdown=5)
    assert isinstance(task_id, str)
    assert task_id


def test_in_memory_dispatch_accumulates():
    bus = InMemoryTaskBus()
    bus.dispatch("task.a", {})
    bus.dispatch("task.b", {"x": 1})
    assert len(bus.dispatched) == 2
    assert bus.dispatched[0].task_name == "task.a"
    assert bus.dispatched[1].task_name == "task.b"


def test_in_memory_dispatch_stores_queue_and_countdown():
    bus = InMemoryTaskBus()
    bus.dispatch("task", {"a": 1}, queue="critical", countdown=30)
    d = bus.dispatched[0]
    assert d.queue == "critical"
    assert d.countdown == 30
    assert d.payload == {"a": 1}


def test_in_memory_clear():
    bus = InMemoryTaskBus()
    bus.dispatch("t", {})
    bus.clear()
    assert bus.dispatched == []


def test_in_memory_default_queue():
    bus = InMemoryTaskBus()
    bus.dispatch("t", {})
    assert bus.dispatched[0].queue == "default"
    assert bus.dispatched[0].countdown == 0


# ---------------------------------------------------------------------------
# CeleryTaskBus (mocked)
# ---------------------------------------------------------------------------


def _mock_celery_app(task_id: str = "celery-task-123") -> MagicMock:
    app = MagicMock()
    result = MagicMock()
    result.id = task_id
    app.send_task = MagicMock(return_value=result)
    return app


def test_celery_dispatch_calls_send_task():
    app = _mock_celery_app("tid-1")
    bus = CeleryTaskBus.__new__(CeleryTaskBus)
    bus._app = app

    task_id = bus.dispatch("my.task", {"x": 1}, queue="default", countdown=0)
    assert task_id == "tid-1"
    app.send_task.assert_called_once_with(
        "my.task",
        kwargs={"x": 1},
        queue="default",
        countdown=0,
    )


def test_celery_dispatch_custom_queue():
    app = _mock_celery_app("tid-2")
    bus = CeleryTaskBus.__new__(CeleryTaskBus)
    bus._app = app

    bus.dispatch("email.send", {"to": "x@y.com"}, queue="emails", countdown=10)
    app.send_task.assert_called_once()
    call_kwargs = app.send_task.call_args[1]
    assert call_kwargs["queue"] == "emails"
    assert call_kwargs["countdown"] == 10


# ---------------------------------------------------------------------------
# CeleryResultBackend (mocked)
# ---------------------------------------------------------------------------


def test_result_backend_get_result_success():
    app = MagicMock()
    async_result = MagicMock()
    async_result.status = "SUCCESS"
    async_result.result = {"data": 42}
    app.AsyncResult = MagicMock(return_value=async_result)

    backend = CeleryResultBackend.__new__(CeleryResultBackend)
    backend._app = app

    result = asyncio.run(backend.get_result("tid"))
    assert result.task_id == "tid"
    assert result.status == TaskStatus.SUCCESS
    assert result.result == {"data": 42}
    assert result.error is None


def test_result_backend_get_result_failure():
    app = MagicMock()
    async_result = MagicMock()
    async_result.status = "FAILURE"
    async_result.result = ValueError("boom")
    app.AsyncResult = MagicMock(return_value=async_result)

    backend = CeleryResultBackend.__new__(CeleryResultBackend)
    backend._app = app

    result = asyncio.run(backend.get_result("tid"))
    assert result.status == TaskStatus.FAILURE
    assert "boom" in result.error


def test_result_backend_is_ready():
    app = MagicMock()
    async_result = MagicMock()
    async_result.ready.return_value = True
    app.AsyncResult = MagicMock(return_value=async_result)

    backend = CeleryResultBackend.__new__(CeleryResultBackend)
    backend._app = app

    assert backend.is_ready("tid") is True


def test_result_backend_revoke():
    app = MagicMock()
    app.control = MagicMock()
    backend = CeleryResultBackend.__new__(CeleryResultBackend)
    backend._app = app

    backend.revoke("tid")
    app.control.revoke.assert_called_once_with("tid", terminate=False)
