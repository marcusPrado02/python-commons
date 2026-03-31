"""Unit tests for adapter health checks (R-05)."""
from __future__ import annotations

import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mp_commons.observability.health.adapters import (
    ElasticsearchHealthCheck,
    KafkaHealthCheck,
    NatsHealthCheck,
    RabbitMQHealthCheck,
)


# ---------------------------------------------------------------------------
# KafkaHealthCheck
# ---------------------------------------------------------------------------


class TestKafkaHealthCheck:
    def _check(self) -> KafkaHealthCheck:
        return KafkaHealthCheck("localhost:9092")

    def test_name(self):
        assert self._check().name == "kafka"

    async def test_healthy_when_connected(self):
        check = self._check()
        admin_mock = MagicMock()
        admin_mock.start = AsyncMock()
        admin_mock.close = AsyncMock()
        admin_mock.list_topics = AsyncMock(return_value=["t1", "t2"])

        with patch.dict(
            sys.modules,
            {
                "aiokafka": MagicMock(),
                "aiokafka.admin": MagicMock(AIOKafkaAdminClient=MagicMock(return_value=admin_mock)),
            },
        ):
            status = await check.check()

        assert status.healthy
        assert "2 topic(s)" in (status.detail or "")

    async def test_unhealthy_when_connection_fails(self):
        check = self._check()
        admin_mock = MagicMock()
        admin_mock.start = AsyncMock(side_effect=OSError("refused"))
        admin_mock.close = AsyncMock()

        with patch.dict(
            sys.modules,
            {
                "aiokafka": MagicMock(),
                "aiokafka.admin": MagicMock(AIOKafkaAdminClient=MagicMock(return_value=admin_mock)),
            },
        ):
            status = await check.check()

        assert not status.healthy
        assert "refused" in (status.detail or "")

    async def test_unhealthy_when_not_installed(self):
        check = self._check()
        with patch.dict(sys.modules, {"aiokafka": None}):
            status = await check.check()
        assert not status.healthy
        assert "not installed" in (status.detail or "")


# ---------------------------------------------------------------------------
# NatsHealthCheck
# ---------------------------------------------------------------------------


class TestNatsHealthCheck:
    def _check(self) -> NatsHealthCheck:
        return NatsHealthCheck("nats://localhost:4222")

    def test_name(self):
        assert self._check().name == "nats"

    async def test_healthy_when_connected(self):
        check = self._check()
        nc_mock = MagicMock()
        nc_mock.connected_url = "nats://localhost:4222"
        nc_mock.drain = AsyncMock()
        nats_mod = MagicMock()
        nats_mod.connect = AsyncMock(return_value=nc_mock)

        with patch.dict(sys.modules, {"nats": nats_mod}):
            status = await check.check()

        assert status.healthy

    async def test_unhealthy_when_not_installed(self):
        check = self._check()
        with patch.dict(sys.modules, {"nats": None}):
            status = await check.check()
        assert not status.healthy

    async def test_unhealthy_on_connection_error(self):
        check = self._check()
        nats_mod = MagicMock()
        nats_mod.connect = AsyncMock(side_effect=ConnectionRefusedError("refused"))

        with patch.dict(sys.modules, {"nats": nats_mod}):
            status = await check.check()

        assert not status.healthy


# ---------------------------------------------------------------------------
# RabbitMQHealthCheck
# ---------------------------------------------------------------------------


class TestRabbitMQHealthCheck:
    def _check(self) -> RabbitMQHealthCheck:
        return RabbitMQHealthCheck()

    def test_name(self):
        assert self._check().name == "rabbitmq"

    async def test_healthy_on_200(self):
        check = self._check()
        response = MagicMock()
        response.status_code = 200
        http_client = MagicMock()
        http_client.__aenter__ = AsyncMock(return_value=http_client)
        http_client.__aexit__ = AsyncMock(return_value=None)
        http_client.get = AsyncMock(return_value=response)

        import mp_commons.observability.health.adapters as _mod

        with patch.dict(sys.modules, {"httpx": MagicMock(AsyncClient=MagicMock(return_value=http_client))}):
            status = await check.check()

        assert status.healthy

    async def test_unhealthy_on_non_200(self):
        check = self._check()
        response = MagicMock()
        response.status_code = 503
        http_client = MagicMock()
        http_client.__aenter__ = AsyncMock(return_value=http_client)
        http_client.__aexit__ = AsyncMock(return_value=None)
        http_client.get = AsyncMock(return_value=response)

        with patch.dict(sys.modules, {"httpx": MagicMock(AsyncClient=MagicMock(return_value=http_client))}):
            status = await check.check()

        assert not status.healthy
        assert "503" in (status.detail or "")


# ---------------------------------------------------------------------------
# ElasticsearchHealthCheck
# ---------------------------------------------------------------------------


class TestElasticsearchHealthCheck:
    def _check(self) -> ElasticsearchHealthCheck:
        return ElasticsearchHealthCheck()

    def test_name(self):
        assert self._check().name == "elasticsearch"

    async def test_healthy_on_green_status(self):
        check = self._check()
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"status": "green"}
        http_client = MagicMock()
        http_client.__aenter__ = AsyncMock(return_value=http_client)
        http_client.__aexit__ = AsyncMock(return_value=None)
        http_client.get = AsyncMock(return_value=response)

        with patch.dict(sys.modules, {"httpx": MagicMock(AsyncClient=MagicMock(return_value=http_client))}):
            status = await check.check()

        assert status.healthy
        assert "green" in (status.detail or "")

    async def test_unhealthy_on_red_status(self):
        check = self._check()
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"status": "red"}
        http_client = MagicMock()
        http_client.__aenter__ = AsyncMock(return_value=http_client)
        http_client.__aexit__ = AsyncMock(return_value=None)
        http_client.get = AsyncMock(return_value=response)

        with patch.dict(sys.modules, {"httpx": MagicMock(AsyncClient=MagicMock(return_value=http_client))}):
            status = await check.check()

        assert not status.healthy
