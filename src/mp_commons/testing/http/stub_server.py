"""HTTP stub server built on top of respx.MockRouter."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

__all__ = [
    "HttpStubServer",
    "StubCallCountError",
]


class StubCallCountError(AssertionError):
    """Raised when a stubbed URL was called an unexpected number of times."""


class HttpStubServer:
    """Fluent wrapper around ``respx.MockRouter`` for use in tests.

    Usage::

        with HttpStubServer() as stub:
            stub.stub_get("https://api.example.com/data", {"key": "value"})
            # ... call your code that uses httpx ...
            stub.assert_called("https://api.example.com/data", times=1)
    """

    def __init__(self) -> None:
        try:
            import respx  # noqa: F401
        except ImportError as exc:
            raise ImportError("pip install respx") from exc
        self._router: Any = None
        self._call_counts: dict[str, int] = {}

    def __enter__(self) -> HttpStubServer:
        import respx

        self._router = respx.mock(assert_all_called=False).__enter__()
        return self

    def __exit__(self, *args: Any) -> None:
        if self._router is not None:
            self._router.__exit__(*args)

    # async context manager support
    async def __aenter__(self) -> HttpStubServer:
        import respx

        self._router = await respx.mock(assert_all_called=False).__aenter__()
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._router is not None:
            await self._router.__aexit__(*args)

    def stub_get(
        self,
        url: str,
        response_json: Any = None,
        status: int = 200,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Register a GET stub for *url*."""
        import httpx

        _url = url
        _call_counts = self._call_counts

        def _side_effect(request: Any, *args: Any, **kwargs: Any) -> Any:
            _call_counts[_url] = _call_counts.get(_url, 0) + 1
            return httpx.Response(status, json=response_json, headers=headers or {})

        self._router.get(url).mock(side_effect=_side_effect)

    def stub_post(
        self,
        url: str,
        response_fn: Callable[[Any], Any] | None = None,
        response_json: Any = None,
        status: int = 200,
    ) -> None:
        """Register a POST stub for *url*."""
        import httpx

        _url = url
        _call_counts = self._call_counts

        def _side_effect(request: Any, *args: Any, **kwargs: Any) -> Any:
            _call_counts[_url] = _call_counts.get(_url, 0) + 1
            if response_fn is not None:
                return response_fn(request)
            return httpx.Response(status, json=response_json)

        self._router.post(url).mock(side_effect=_side_effect)

    def stub_any(
        self,
        method: str,
        url: str,
        response_json: Any = None,
        status: int = 200,
    ) -> None:
        """Register a stub for any HTTP method."""
        import httpx

        _url = url
        _call_counts = self._call_counts

        def _side_effect(request: Any, *args: Any, **kwargs: Any) -> Any:
            _call_counts[_url] = _call_counts.get(_url, 0) + 1
            return httpx.Response(status, json=response_json)

        getattr(self._router, method.lower())(url).mock(side_effect=_side_effect)

    def assert_called(self, url: str, times: int = 1) -> None:
        """Assert that *url* was called exactly *times* times."""
        actual = self._call_counts.get(url, 0)
        if actual != times:
            raise StubCallCountError(f"{url!r} was called {actual} time(s), expected {times}")

    def call_count(self, url: str) -> int:
        return self._call_counts.get(url, 0)

    def reset(self) -> None:
        self._call_counts.clear()
