"""Application pipeline – Pipeline class."""
from __future__ import annotations

from typing import Any

from mp_commons.application.pipeline.middleware import Handler, Middleware


class Pipeline:
    """Builds and executes an ordered chain of middleware around a handler."""

    def __init__(self) -> None:
        self._middlewares: list[Middleware] = []

    def add(self, middleware: Middleware) -> "Pipeline":
        """Append a middleware (fluent API)."""
        self._middlewares.append(middleware)
        return self

    async def execute(self, request: Any, handler: Handler) -> Any:
        """Execute the full chain, ending with *handler*."""
        chain = handler
        for mw in reversed(self._middlewares):
            _next = chain
            _mw = mw

            async def _wrap(req: Any, *, _n: Handler = _next, _m: Middleware = _mw) -> Any:
                return await _m(req, _n)

            chain = _wrap
        return await chain(request)


__all__ = ["Pipeline"]
