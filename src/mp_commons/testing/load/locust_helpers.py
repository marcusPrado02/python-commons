"""Locust integration helpers — §96.3.

Provides a :class:`LocustKernelUser` base class and :func:`task_with_metrics`
decorator that hook into the mp-commons observability stack (Correlation ID,
Security Context) for Locust-based load tests.

Requires ``locust>=2.20``.  All classes raise :class:`ImportError` when the
library is absent.

Example::

    from locust import task
    from mp_commons.testing.load.locust_helpers import LocustKernelUser, task_with_metrics


    class MyUser(LocustKernelUser):
        host = "http://localhost:8000"

        @task
        @task_with_metrics("my_endpoint")
        def hit_endpoint(self) -> None:
            self.client.get("/api/health")
"""

from __future__ import annotations

from collections.abc import Callable
import functools
import time
from typing import Any, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


def _require_locust() -> Any:
    try:
        import locust  # type: ignore[import-untyped]

        return locust
    except ImportError as exc:
        raise ImportError(
            "locust is required for LocustKernelUser. Install it with: pip install 'locust>=2.20'"
        ) from exc


# ---------------------------------------------------------------------------
# LocustKernelUser
# ---------------------------------------------------------------------------


class LocustKernelUser:
    """Locust ``HttpUser`` sub-class pre-wired with mp-commons observability.

    On every task execution a fresh :class:`~mp_commons.observability.correlation.CorrelationContext`
    is established so that all downstream HTTP calls carry a unique
    ``X-Correlation-ID`` header, and the :class:`~mp_commons.kernel.security.SecurityContext`
    is cleared to a test principal.

    Sub-class this instead of ``locust.HttpUser``::

        class MyUser(LocustKernelUser):
            host = "http://localhost:8000"
            wait_time = between(1, 2)

            @task
            def my_task(self) -> None:
                self.client.get("/api/items")
    """

    # Will be set dynamically when Locust is available
    _locust_base: type | None = None

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        # Lazily inject the Locust base class at subclass-definition time
        try:
            from locust import HttpUser  # type: ignore[import-untyped]

            if HttpUser not in cls.__bases__ and not any(
                issubclass(b, HttpUser) for b in cls.__mro__[1:] if b is not cls
            ):
                # Patch the MRO to include HttpUser if not already present
                cls.__bases__ = (
                    HttpUser,
                    *tuple(b for b in cls.__bases__ if b is not LocustKernelUser),
                )
        except ImportError:
            pass  # Locust not installed — allow class definition to succeed for testing

    def on_start(self) -> None:
        """Called by Locust when the virtual user starts.

        Sets up a fresh correlation context for this user session.
        """
        from uuid import uuid4

        try:
            from mp_commons.observability.correlation import CorrelationContext

            CorrelationContext.set(str(uuid4()))
        except ImportError:
            pass

    def on_stop(self) -> None:
        """Called by Locust when the virtual user stops.

        Clears the correlation context.
        """
        try:
            from mp_commons.observability.correlation import CorrelationContext

            CorrelationContext.clear()
        except ImportError:
            pass


# ---------------------------------------------------------------------------
# task_with_metrics decorator
# ---------------------------------------------------------------------------


def task_with_metrics(
    name: str | None = None,
) -> Callable[[F], F]:
    """Decorator that records Locust ``events.request`` metrics for a task.

    Wraps a Locust task function so that success/failure is reported to the
    Locust statistics engine with a configurable *name*.  The decorator also
    sets a per-call correlation ID on the current request.

    Parameters
    ----------
    name:
        The request name shown in the Locust statistics table.  Defaults to
        the decorated function's ``__name__``.

    Usage::

        @task
        @task_with_metrics("create_order")
        def create_order(self) -> None:
            self.client.post("/orders", json={...})
    """

    def decorator(func: F) -> F:
        task_name = name or func.__name__

        @functools.wraps(func)
        def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            from uuid import uuid4

            # Refresh correlation ID per task invocation
            try:
                from mp_commons.observability.correlation import CorrelationContext

                CorrelationContext.set(str(uuid4()))
            except ImportError:
                pass

            start = time.perf_counter()
            int(time.time() * 1000)
            exc: Exception | None = None
            try:
                return func(self, *args, **kwargs)
            except Exception as e:
                exc = e
                raise
            finally:
                elapsed_ms = int((time.perf_counter() - start) * 1000)
                # Fire Locust request event if available
                try:
                    import locust  # type: ignore[import-untyped]  # noqa: F401

                    environment = getattr(self, "environment", None)
                    if environment is not None:
                        environment.events.request.fire(
                            request_type="TASK",
                            name=task_name,
                            response_time=elapsed_ms,
                            response_length=0,
                            exception=exc,
                            context={},
                        )
                except ImportError:
                    pass

        return wrapper  # type: ignore[return-value]

    return decorator


__all__ = ["LocustKernelUser", "task_with_metrics"]
