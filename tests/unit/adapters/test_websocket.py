"""Unit tests for the WebSocket hub adapter (§53)."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from mp_commons.adapters.websocket.hub import ConnectionHub, GroupManager, WebSocketMiddleware


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_conn(conn_id: str) -> MagicMock:
    conn = MagicMock()
    conn.id = conn_id
    conn.send = AsyncMock()
    return conn


# ---------------------------------------------------------------------------
# ConnectionHub
# ---------------------------------------------------------------------------


def test_hub_register_and_count():
    hub = ConnectionHub()
    conn = _mock_conn("c1")

    async def run():
        await hub.register(conn)
        assert hub.connection_count == 1

    asyncio.run(run())


def test_hub_unregister_removes():
    hub = ConnectionHub()
    conn = _mock_conn("c1")

    async def run():
        await hub.register(conn)
        await hub.unregister(conn)
        assert hub.connection_count == 0

    asyncio.run(run())


def test_hub_unregister_noop_on_missing():
    hub = ConnectionHub()
    conn = _mock_conn("absent")

    async def run():
        await hub.unregister(conn)  # should not raise

    asyncio.run(run())


def test_hub_broadcast_reaches_all():
    hub = ConnectionHub()
    c1 = _mock_conn("c1")
    c2 = _mock_conn("c2")

    async def run():
        await hub.register(c1)
        await hub.register(c2)
        await hub.broadcast("hello")

    asyncio.run(run())
    c1.send.assert_called_once_with("hello")
    c2.send.assert_called_once_with("hello")


def test_hub_send_to_specific():
    hub = ConnectionHub()
    c1 = _mock_conn("c1")
    c2 = _mock_conn("c2")

    async def run():
        await hub.register(c1)
        await hub.register(c2)
        await hub.send_to("c1", "private")

    asyncio.run(run())
    c1.send.assert_called_once_with("private")
    c2.send.assert_not_called()


def test_hub_send_to_missing_id_noop():
    hub = ConnectionHub()

    async def run():
        await hub.send_to("ghost", "data")  # should not raise

    asyncio.run(run())


def test_hub_group_broadcast():
    hub = ConnectionHub()
    gm = GroupManager()
    c1 = _mock_conn("c1")
    c2 = _mock_conn("c2")
    c3 = _mock_conn("c3")

    async def run():
        await hub.register(c1)
        await hub.register(c2)
        await hub.register(c3)
        gm.join("c1", "room1")
        gm.join("c2", "room1")
        await hub.group_broadcast("room1", "to room", group_manager=gm)

    asyncio.run(run())
    c1.send.assert_called_once_with("to room")
    c2.send.assert_called_once_with("to room")
    c3.send.assert_not_called()


def test_hub_group_broadcast_missing_group():
    hub = ConnectionHub()
    gm = GroupManager()
    c1 = _mock_conn("c1")

    async def run():
        await hub.register(c1)
        await hub.group_broadcast("empty-group", "msg", group_manager=gm)

    asyncio.run(run())
    c1.send.assert_not_called()


# ---------------------------------------------------------------------------
# GroupManager
# ---------------------------------------------------------------------------


def test_group_manager_join_adds_member():
    gm = GroupManager()
    gm.join("c1", "g1")
    assert "c1" in gm.members("g1")


def test_group_manager_leave_removes():
    gm = GroupManager()
    gm.join("c1", "g1")
    gm.leave("c1", "g1")
    assert "c1" not in gm.members("g1")


def test_group_manager_members_returns_frozenset():
    gm = GroupManager()
    gm.join("c1", "g1")
    gm.join("c2", "g1")
    members = gm.members("g1")
    assert "c1" in members
    assert "c2" in members


def test_group_manager_empty_group_returns_empty():
    gm = GroupManager()
    assert gm.members("no-such-group") == frozenset()


def test_group_manager_groups_for():
    gm = GroupManager()
    gm.join("c1", "g1")
    gm.join("c1", "g2")
    assert gm.groups_for("c1") == {"g1", "g2"}


def test_group_manager_leave_noop():
    gm = GroupManager()
    gm.leave("ghost", "group")  # should not raise


# ---------------------------------------------------------------------------
# WebSocketMiddleware
# ---------------------------------------------------------------------------


def test_ws_middleware_passes_through_non_ws():
    inner = AsyncMock()
    mw = WebSocketMiddleware(inner)
    scope = {"type": "http"}

    asyncio.run(mw(scope, None, None))
    inner.assert_called_once_with(scope, None, None)


def test_ws_middleware_calls_app_for_ws():
    inner = AsyncMock()
    mw = WebSocketMiddleware(inner)
    scope = {"type": "websocket", "headers": [(b"x-correlation-id", b"corr-1")]}

    asyncio.run(mw(scope, None, None))
    inner.assert_called_once()
