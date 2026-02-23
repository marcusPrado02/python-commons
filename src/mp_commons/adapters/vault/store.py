"""HashiCorp Vault adapter – VaultSecretStore and VaultTokenRenewer."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from mp_commons.config.secrets import SecretRef, SecretStore

logger = logging.getLogger(__name__)


def _require_hvac() -> Any:
    try:
        import hvac  # type: ignore[import-untyped]
        return hvac
    except ImportError as exc:
        raise ImportError("Install 'mp-commons[vault]' (hvac) to use the Vault adapter") from exc


class VaultSecretStore(SecretStore):
    """HashiCorp Vault KV v2 secret backend."""

    def __init__(self, url: str = "http://127.0.0.1:8200", token: str | None = None, mount_point: str = "secret", **kwargs: Any) -> None:
        hvac = _require_hvac()
        self._client = hvac.Client(url=url, token=token, **kwargs)
        self._mount = mount_point

    async def get(self, ref: SecretRef) -> str:
        import asyncio
        return await asyncio.get_event_loop().run_in_executor(None, self._sync_get, ref)

    def _sync_get(self, ref: SecretRef) -> str:
        response = self._client.secrets.kv.v2.read_secret_version(path=ref.path, mount_point=self._mount)
        data: dict[str, str] = response["data"]["data"]
        if ref.key not in data:
            raise KeyError(f"Key '{ref.key}' not found at path '{ref.path}'")
        return data[ref.key]

    async def get_all(self, path: str) -> dict[str, str]:
        import asyncio
        return await asyncio.get_event_loop().run_in_executor(None, self._sync_get_all, path)

    def _sync_get_all(self, path: str) -> dict[str, str]:
        response = self._client.secrets.kv.v2.read_secret_version(path=path, mount_point=self._mount)
        return response["data"]["data"]


class VaultTokenRenewer:
    """Background asyncio task that renews the Vault token before it expires.

    Usage::

        async with VaultTokenRenewer(vault_client) as renewer:
            ...  # token renewed automatically in background
    """

    def __init__(
        self,
        client: Any,
        *,
        renew_before_seconds: int = 300,
        check_interval: float = 60.0,
    ) -> None:
        self._client = client
        self._renew_before = renew_before_seconds
        self._interval = check_interval
        self._task: asyncio.Task[None] | None = None
        self._running = False

    async def start(self) -> None:
        """Start the background renewal loop."""
        self._running = True
        self._task = asyncio.create_task(self._renew_loop())

    async def stop(self) -> None:
        """Stop the background renewal loop."""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def __aenter__(self) -> "VaultTokenRenewer":
        await self.start()
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.stop()

    async def _renew_loop(self) -> None:
        while self._running:
            try:
                info = self._client.auth.token.lookup_self()
                ttl: int = info["data"]["ttl"]
                if ttl <= self._renew_before:
                    self._client.auth.token.renew_self()
                    logger.debug("vault.token_renewed remaining_ttl=%d", ttl)
                else:
                    logger.debug("vault.token_ok remaining_ttl=%d", ttl)
            except Exception as exc:
                logger.warning("vault.token_renew_failed exc=%r", exc)
            await asyncio.sleep(self._interval)


__all__ = ["VaultSecretStore", "VaultTokenRenewer"]
