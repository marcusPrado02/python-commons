"""HashiCorp Vault adapter – VaultSecretStore."""
from __future__ import annotations

from typing import Any

from mp_commons.config.secrets import SecretRef, SecretStore


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


__all__ = ["VaultSecretStore"]
