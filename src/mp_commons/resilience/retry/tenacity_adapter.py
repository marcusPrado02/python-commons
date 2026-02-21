"""Resilience – TenacityRetryPolicy adapter (§15.6).

Optional dependency: ``tenacity``.  Install with::

    pip install mp-commons[tenacity]
"""
from __future__ import annotations

from typing import Any, Awaitable, Callable, TypeVar

T = TypeVar("T")


class TenacityRetryPolicy:
    """Retry policy backed by the ``tenacity`` library.

    Provides the same ``execute`` / ``execute_async`` interface as
    :class:`~mp_commons.resilience.retry.policy.RetryPolicy` so the two are
    interchangeable in application code.

    Parameters
    ----------
    max_attempts:
        Maximum number of call attempts (including the first call).
    wait:
        A ``tenacity`` wait strategy, e.g.
        ``tenacity.wait_exponential(multiplier=1, max=10)``.
        Defaults to ``wait_fixed(1)``.
    retry:
        A ``tenacity`` retry predicate, e.g.
        ``tenacity.retry_if_exception_type(IOError)``.
        Defaults to ``retry_if_exception(lambda e: True)`` — retry on any
        exception.
    reraise:
        Whether to re-raise the original exception after all attempts are
        exhausted.  Defaults to ``True``.
    kwargs:
        Additional keyword arguments forwarded directly to
        :func:`tenacity.Retrying` / :func:`tenacity.AsyncRetrying`.

    Example
    -------
    ::

        from tenacity import wait_exponential, retry_if_exception_type
        policy = TenacityRetryPolicy(
            max_attempts=5,
            wait=wait_exponential(multiplier=0.5, max=8),
            retry=retry_if_exception_type(IOError),
        )
        result = await policy.execute_async(my_async_fn)
    """

    def __init__(
        self,
        max_attempts: int = 3,
        wait: Any = None,
        retry: Any = None,
        reraise: bool = True,
        **kwargs: Any,
    ) -> None:
        try:
            import tenacity  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "Install 'tenacity' (pip install tenacity) to use TenacityRetryPolicy"
            ) from exc

        import tenacity as ten

        self._max_attempts = max_attempts
        self._wait = wait or ten.wait_fixed(1)
        self._retry = retry or ten.retry_if_exception(lambda _: True)
        self._reraise = reraise
        self._extra_kwargs = kwargs

    def _build_retrying(self) -> Any:
        import tenacity as ten

        return ten.Retrying(
            stop=ten.stop_after_attempt(self._max_attempts),
            wait=self._wait,
            retry=self._retry,
            reraise=self._reraise,
            **self._extra_kwargs,
        )

    def _build_async_retrying(self) -> Any:
        import tenacity as ten

        return ten.AsyncRetrying(
            stop=ten.stop_after_attempt(self._max_attempts),
            wait=self._wait,
            retry=self._retry,
            reraise=self._reraise,
            **self._extra_kwargs,
        )

    def execute(self, func: Callable[[], T]) -> T:
        """Execute *func* synchronously with tenacity retry."""
        return self._build_retrying()(func)

    async def execute_async(self, func: Callable[[], Awaitable[T]]) -> T:
        """Execute *func* asynchronously with tenacity retry."""
        async for attempt in self._build_async_retrying():
            with attempt:
                result = await func()
        return result  # type: ignore[return-value]


__all__ = ["TenacityRetryPolicy"]
