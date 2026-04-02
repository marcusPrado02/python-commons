"""Structured health checks for common infrastructure adapters (R-05).

Provides ready-made :class:`~mp_commons.observability.health.HealthCheck`
implementations for Kafka, NATS, RabbitMQ, and Elasticsearch.  Each check
attempts a lightweight probe (metadata request, ping, admin call) and returns
a :class:`~mp_commons.observability.health.HealthStatus`.

Usage::

    from mp_commons.observability.health.adapters import KafkaHealthCheck
    from mp_commons.observability.health import HealthRegistry

    registry = HealthRegistry()
    registry.register(KafkaHealthCheck(bootstrap_servers="localhost:9092"))
    report = await registry.run_all()
"""

from __future__ import annotations

from mp_commons.observability.health.check import HealthCheck, HealthStatus

# ---------------------------------------------------------------------------
# Kafka health check
# ---------------------------------------------------------------------------


class KafkaHealthCheck(HealthCheck):
    """Check Kafka connectivity by fetching cluster metadata.

    Parameters
    ----------
    bootstrap_servers:
        Kafka bootstrap server address, e.g. ``"localhost:9092"``.
    timeout_ms:
        Request timeout in milliseconds. Default: ``5000``.
    """

    def __init__(self, bootstrap_servers: str, timeout_ms: int = 5000) -> None:
        self._bootstrap_servers = bootstrap_servers
        self._timeout_ms = timeout_ms

    @property
    def name(self) -> str:
        return "kafka"

    async def check(self) -> HealthStatus:
        try:
            from aiokafka.admin import AIOKafkaAdminClient  # type: ignore[import-untyped]
        except ImportError:
            return HealthStatus(healthy=False, detail="aiokafka not installed")

        client = AIOKafkaAdminClient(
            bootstrap_servers=self._bootstrap_servers,
            request_timeout_ms=self._timeout_ms,
        )
        try:
            await client.start()
            topics = await client.list_topics()
            return HealthStatus(healthy=True, detail=f"connected; {len(topics)} topic(s)")
        except Exception as exc:
            return HealthStatus(healthy=False, detail=str(exc))
        finally:
            try:
                await client.close()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# NATS health check
# ---------------------------------------------------------------------------


class NatsHealthCheck(HealthCheck):
    """Check NATS connectivity by opening a connection and pinging the server.

    Parameters
    ----------
    servers:
        NATS server URL or list of URLs, e.g. ``"nats://localhost:4222"``.
    connect_timeout:
        Connection timeout in seconds. Default: ``3.0``.
    """

    def __init__(
        self,
        servers: str | list[str] = "nats://localhost:4222",
        connect_timeout: float = 3.0,
    ) -> None:
        self._servers = servers
        self._connect_timeout = connect_timeout

    @property
    def name(self) -> str:
        return "nats"

    async def check(self) -> HealthStatus:
        try:
            import nats  # type: ignore[import-untyped]
        except ImportError:
            return HealthStatus(healthy=False, detail="nats-py not installed")

        nc = None
        try:
            nc = await nats.connect(
                servers=self._servers,
                connect_timeout=self._connect_timeout,
            )
            info = nc.connected_url
            return HealthStatus(healthy=True, detail=f"connected to {info}")
        except Exception as exc:
            return HealthStatus(healthy=False, detail=str(exc))
        finally:
            if nc is not None:
                try:
                    await nc.drain()
                except Exception:
                    pass


# ---------------------------------------------------------------------------
# RabbitMQ health check
# ---------------------------------------------------------------------------


class RabbitMQHealthCheck(HealthCheck):
    """Check RabbitMQ connectivity via the management HTTP API.

    Parameters
    ----------
    url:
        RabbitMQ management API base URL,
        e.g. ``"http://guest:guest@localhost:15672"``.
    timeout:
        HTTP request timeout in seconds. Default: ``5.0``.
    """

    def __init__(
        self, url: str = "http://guest:guest@localhost:15672", timeout: float = 5.0
    ) -> None:
        self._url = url.rstrip("/")
        self._timeout = timeout

    @property
    def name(self) -> str:
        return "rabbitmq"

    async def check(self) -> HealthStatus:
        try:
            import httpx  # type: ignore[import-untyped]
        except ImportError:
            return HealthStatus(healthy=False, detail="httpx not installed")

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(f"{self._url}/api/aliveness-test/%2F")
                if response.status_code == 200:
                    return HealthStatus(healthy=True, detail="alive")
                return HealthStatus(
                    healthy=False,
                    detail=f"management API returned {response.status_code}",
                )
        except Exception as exc:
            return HealthStatus(healthy=False, detail=str(exc))


# ---------------------------------------------------------------------------
# Elasticsearch health check
# ---------------------------------------------------------------------------


class ElasticsearchHealthCheck(HealthCheck):
    """Check Elasticsearch connectivity using the cluster health API.

    Parameters
    ----------
    hosts:
        Elasticsearch host URL, e.g. ``"http://localhost:9200"``.
    timeout:
        HTTP request timeout in seconds. Default: ``5.0``.
    """

    def __init__(self, hosts: str = "http://localhost:9200", timeout: float = 5.0) -> None:
        self._hosts = hosts
        self._timeout = timeout

    @property
    def name(self) -> str:
        return "elasticsearch"

    async def check(self) -> HealthStatus:
        try:
            import httpx  # type: ignore[import-untyped]
        except ImportError:
            return HealthStatus(healthy=False, detail="httpx not installed")

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(f"{self._hosts.rstrip('/')}/_cluster/health")
                if response.status_code == 200:
                    data = response.json()
                    status = data.get("status", "unknown")
                    healthy = status in ("green", "yellow")
                    return HealthStatus(healthy=healthy, detail=f"cluster status: {status}")
                return HealthStatus(
                    healthy=False,
                    detail=f"health endpoint returned {response.status_code}",
                )
        except Exception as exc:
            return HealthStatus(healthy=False, detail=str(exc))


__all__ = [
    "ElasticsearchHealthCheck",
    "KafkaHealthCheck",
    "NatsHealthCheck",
    "RabbitMQHealthCheck",
]
