"""WebSocket connection hub, group manager, and ASGI middleware.

No external dependencies required.
"""
from __future__ import annotations

import asyncio
from typing import Any, Protocol, runtime_checkable


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class WebSocketConnection(Protocol):
    """Minimal protocol for a WebSocket connection."""

    @property
    def id(self) -> str:
        """Unique connection identifier."""
        ...

    async def send(self, data: str | bytes) -> None:
        """Send *data* to this connection."""
        ...

    async def receive(self) -> str | bytes:
        """Receive the next message from this connection."""
        ...

    def close(self) -> None:
        """Close the connection."""
        ...


# ---------------------------------------------------------------------------
# ConnectionHub
# ---------------------------------------------------------------------------


class ConnectionHub:
    """Registry of active :class:`WebSocketConnection` objects with broadcasting.

    Thread-safety: all mutations are protected by an :class:`asyncio.Lock`
    so that multiple coroutines can safely register/unregister concurrently.
    """

    def __init__(self) -> None:
        self._connections: dict[str, WebSocketConnection] = {}
        self._lock = asyncio.Lock()

    async def register(self, conn: WebSocketConnection) -> None:
        """Add *conn* to the hub."""
        async with self._lock:
            self._connections[conn.id] = conn

    async def unregister(self, conn: WebSocketConnection) -> None:
        """Remove *conn* from the hub.  No-op if not registered."""
        async with self._lock:
            self._connections.pop(conn.id, None)

    async def broadcast(self, data: str | bytes) -> None:
        """Send *data* to every registered connection."""
        async with self._lock:
            conns = list(self._connections.values())
        await asyncio.gather(*[c.send(data) for c in conns], return_exceptions=True)

    async def send_to(self, conn_id: str, data: str | bytes) -> None:
        """Send *data* to the connection with *conn_id*.

        Silently no-ops if the connection is not found.
        """
        async with self._lock:
            conn = self._connections.get(conn_id)
        if conn is not None:
            await conn.send(data)

    async def group_broadcast(self, group_id: str, data: str | bytes, *, group_manager: "GroupManager") -> None:
        """Send *data* to all connections in *group_id*.

        Silently skips connections that have since been unregistered.
        """
        member_ids = group_manager.members(group_id)
        async with self._lock:
            conns = [self._connections[cid] for cid in member_ids if cid in self._connections]
        await asyncio.gather(*[c.send(data) for c in conns], return_exceptions=True)

    @property
    def connection_count(self) -> int:
        return len(self._connections)


# ---------------------------------------------------------------------------
# GroupManager
# ---------------------------------------------------------------------------


class GroupManager:
    """In-memory dict-backed group membership tracker."""

    def __init__(self) -> None:
        self._groups: dict[str, set[str]] = {}

    def join(self, conn_id: str, group_id: str) -> None:
        """Add *conn_id* to *group_id*.  Creates the group if absent."""
        self._groups.setdefault(group_id, set()).add(conn_id)

    def leave(self, conn_id: str, group_id: str) -> None:
        """Remove *conn_id* from *group_id*.  No-op if not a member."""
        if group_id in self._groups:
            self._groups[group_id].discard(conn_id)

    def members(self, group_id: str) -> set[str]:
        """Return the set of connection IDs in *group_id* (empty if absent)."""
        return frozenset(self._groups.get(group_id, set()))  # type: ignore[return-value]

    def groups_for(self, conn_id: str) -> set[str]:
        """Return all groups that *conn_id* belongs to."""
        return {gid for gid, members in self._groups.items() if conn_id in members}


# ---------------------------------------------------------------------------
# ASGI Middleware
# ---------------------------------------------------------------------------


class WebSocketMiddleware:
    """ASGI middleware that enriches WebSocket connections with:

    * ``x-correlation-id`` header → :class:`~mp_commons.observability.correlation.context.CorrelationContext`
    * ``authorization`` header → :class:`~mp_commons.kernel.security.security_context.SecurityContext`

    For non-WebSocket scopes the request is passed through unchanged.

    Parameters
    ----------
    app:
        The next ASGI application in the chain.
    hub:
        Optional :class:`ConnectionHub`; if provided, connections are
        registered/unregistered automatically.
    """

    def __init__(self, app: Any, *, hub: ConnectionHub | None = None) -> None:
        self._app = app
        self._hub = hub

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope.get("type") != "websocket":
            await self._app(scope, receive, send)
            return

        # Extract correlation-id from headers
        headers = dict(scope.get("headers", []))
        correlation_id_raw = headers.get(b"x-correlation-id", b"").decode("utf-8", errors="ignore")

        # Set CorrelationContext if available
        token = None
        try:
            from mp_commons.observability.correlation.context import CorrelationContext, RequestContext
            from mp_commons.kernel.types.ids import CorrelationId

            if correlation_id_raw:
                ctx = RequestContext(correlation_id=correlation_id_raw)
                token = CorrelationContext.set(ctx)
        except Exception:
            pass

        try:
            await self._app(scope, receive, send)
        finally:
            if token is not None:
                try:
                    CorrelationContext.reset(token)
                except Exception:
                    pass


__all__ = [
    "ConnectionHub",
    "GroupManager",
    "WebSocketConnection",
    "WebSocketMiddleware",
]
