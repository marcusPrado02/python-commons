"""Dynamic config sources and hot-reload registry."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
import os
from pathlib import Path
import time
from typing import Any, Protocol, runtime_checkable

__all__ = [
    "ConfigSource",
    "ConsulConfigSource",
    "DynamicConfigRegistry",
    "EnvConfigSource",
    "FileConfigSource",
]


@runtime_checkable
class ConfigSource(Protocol):
    """Protocol for a dynamic config source."""

    async def load(self) -> dict[str, Any]: ...

    def supports_watch(self) -> bool: ...

    async def watch(self, callback: Callable[[dict[str, Any]], Awaitable[None]]) -> None: ...


# ---------------------------------------------------------------------------
# Implementations
# ---------------------------------------------------------------------------


class EnvConfigSource:
    """Load config from environment variables (optionally filtered by prefix)."""

    def __init__(self, prefix: str = "") -> None:
        self._prefix = prefix.upper()

    async def load(self) -> dict[str, Any]:
        if self._prefix:
            return {
                k[len(self._prefix) :].lower(): v
                for k, v in os.environ.items()
                if k.startswith(self._prefix)
            }
        return dict(os.environ)

    def supports_watch(self) -> bool:
        return False

    async def watch(self, callback: Callable[[dict[str, Any]], Awaitable[None]]) -> None:
        raise NotImplementedError("EnvConfigSource does not support watching")


class FileConfigSource:
    """Load YAML or TOML config from a filesystem path."""

    def __init__(self, path: str | Path, poll_interval_sec: float = 2.0) -> None:
        self._path = Path(path)
        self._poll_interval = poll_interval_sec
        self._last_mtime: float = 0.0

    async def load(self) -> dict[str, Any]:
        suffix = self._path.suffix.lower()
        content = self._path.read_text()
        if suffix in (".yaml", ".yml"):
            import yaml

            return yaml.safe_load(content) or {}
        if suffix == ".toml":
            try:
                import tomllib

                return tomllib.loads(content)
            except ImportError:
                import toml

                return toml.loads(content)
        if suffix == ".json":
            import json

            return json.loads(content)
        raise ValueError(f"Unsupported config file format: {suffix}")

    def supports_watch(self) -> bool:
        try:
            import watchfiles  # noqa: F401

            return True
        except ImportError:
            return False  # fallback to polling

    async def watch(
        self, callback: Callable[[dict[str, Any]], Awaitable[None]]
    ) -> None:  # pragma: no cover
        if self.supports_watch():
            import watchfiles

            async for _changes in watchfiles.awatch(str(self._path)):
                data = await self.load()
                await callback(data)
        else:
            # Polling fallback
            while True:
                mtime = self._path.stat().st_mtime
                if mtime != self._last_mtime:
                    self._last_mtime = mtime
                    data = await self.load()
                    await callback(data)
                await asyncio.sleep(self._poll_interval)


class ConsulConfigSource:
    """Load config from Consul KV (requires httpx)."""

    def __init__(
        self,
        base_url: str = "http://localhost:8500",
        key_prefix: str = "config/",
        poll_interval_sec: float = 5.0,
        token: str | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._key_prefix = key_prefix
        self._poll_interval = poll_interval_sec
        self._headers = {"X-Consul-Token": token} if token else {}
        self._consul_index: int = 0

    async def load(self) -> dict[str, Any]:  # pragma: no cover
        try:
            import base64
            import json

            import httpx
        except ImportError as exc:
            raise ImportError("pip install httpx") from exc

        url = f"{self._base_url}/v1/kv/{self._key_prefix}?recurse"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=self._headers)
        if resp.status_code == 404:
            return {}
        resp.raise_for_status()
        result: dict[str, Any] = {}
        for item in resp.json():
            key = item["Key"].removeprefix(self._key_prefix)
            raw = base64.b64decode(item["Value"]).decode()
            try:
                result[key] = json.loads(raw)
            except Exception:
                result[key] = raw
        return result

    def supports_watch(self) -> bool:
        return True

    async def watch(
        self, callback: Callable[[dict[str, Any]], Awaitable[None]]
    ) -> None:  # pragma: no cover
        try:
            import httpx
        except ImportError as exc:
            raise ImportError("pip install httpx") from exc

        url = f"{self._base_url}/v1/kv/{self._key_prefix}?recurse&wait=10s&index="
        async with httpx.AsyncClient(timeout=15) as client:
            while True:
                resp = await client.get(url + str(self._consul_index), headers=self._headers)
                new_index = int(resp.headers.get("X-Consul-Index", self._consul_index))
                if new_index != self._consul_index:
                    self._consul_index = new_index
                    data = await self.load()
                    await callback(data)


class DynamicConfigRegistry:
    """Central registry serving config values from one or more sources."""

    def __init__(self, ttl_seconds: float = 30.0) -> None:
        self._sources: dict[str, ConfigSource] = {}
        self._cache: dict[str, tuple[Any, float]] = {}  # key -> (value, expires_at)
        self._ttl = ttl_seconds
        self._callbacks: dict[str, list[Callable[[Any], Awaitable[None]]]] = {}

    def register(self, key: str, source: ConfigSource) -> None:
        self._sources[key] = source

    async def get(self, key: str, default: Any = None) -> Any:
        if key in self._cache:
            value, expires_at = self._cache[key]
            if time.monotonic() < expires_at:
                return value
        source = self._sources.get(key)
        if source is None:
            return default
        data = await source.load()
        value = data.get(key, default)
        self._cache[key] = (value, time.monotonic() + self._ttl)
        return value

    def on_change(self, key: str, callback: Callable[[Any], Awaitable[None]]) -> None:
        self._callbacks.setdefault(key, []).append(callback)

    def invalidate(self, key: str) -> None:
        self._cache.pop(key, None)

    def invalidate_all(self) -> None:
        self._cache.clear()
