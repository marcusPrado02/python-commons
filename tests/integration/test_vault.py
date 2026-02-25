"""Integration tests for Vault adapter (§34.3).

Uses testcontainers to spawn a real HashiCorp Vault instance (dev mode).
Run with: PYTHONPATH=src pytest tests/integration/test_vault.py -m integration -v
"""
from __future__ import annotations

import asyncio

import pytest
from testcontainers.vault import VaultContainer

from mp_commons.adapters.vault import VaultSecretStore
from mp_commons.config.secrets import SecretRef


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

ROOT_TOKEN = "toor"  # matches VaultContainer default


def _run(coro):  # type: ignore[no-untyped-def]
    return asyncio.run(coro)


def _vault_url(container: VaultContainer) -> str:
    host = container.get_container_host_ip()
    port = container.get_exposed_port(8200)
    return f"http://{host}:{port}"


def _seed_secret(url: str, path: str, data: dict) -> None:
    """Write a KV v2 secret via the hvac client (synchronous)."""
    import hvac  # type: ignore[import-untyped]

    client = hvac.Client(url=url, token=ROOT_TOKEN)
    # Ensure KV v2 is enabled (dev server has it at 'secret/')
    client.secrets.kv.v2.create_or_update_secret(path=path, secret=data)


# ---------------------------------------------------------------------------
# §34.3 – VaultSecretStore
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestVaultSecretStoreIntegration:
    """Real Vault KV v2 secret store tests."""

    def test_get_returns_stored_value(self) -> None:
        with VaultContainer(root_token=ROOT_TOKEN) as container:
            url = _vault_url(container)
            _seed_secret(url, "myapp/db", {"password": "s3cr3t"})

            async def run() -> str:
                store = VaultSecretStore(url=url, token=ROOT_TOKEN)
                ref = SecretRef(path="myapp/db", key="password")
                return await store.get(ref)

            assert _run(run()) == "s3cr3t"

    def test_get_all_returns_dict(self) -> None:
        with VaultContainer(root_token=ROOT_TOKEN) as container:
            url = _vault_url(container)
            _seed_secret(url, "myapp/multi", {"host": "db.local", "port": "5432"})

            async def run() -> dict:
                store = VaultSecretStore(url=url, token=ROOT_TOKEN)
                return await store.get_all("myapp/multi")

            result = _run(run())
            assert result["host"] == "db.local"
            assert result["port"] == "5432"

    def test_get_missing_key_raises_key_error(self) -> None:
        with VaultContainer(root_token=ROOT_TOKEN) as container:
            url = _vault_url(container)
            _seed_secret(url, "myapp/partial", {"only_key": "value"})

            async def run() -> None:
                store = VaultSecretStore(url=url, token=ROOT_TOKEN)
                ref = SecretRef(path="myapp/partial", key="missing_key")
                await store.get(ref)

            with pytest.raises(KeyError, match="missing_key"):
                _run(run())

    def test_get_multiple_independent_paths(self) -> None:
        with VaultContainer(root_token=ROOT_TOKEN) as container:
            url = _vault_url(container)
            _seed_secret(url, "svc/alpha", {"api_key": "key-alpha"})
            _seed_secret(url, "svc/beta", {"api_key": "key-beta"})

            async def run() -> tuple:
                store = VaultSecretStore(url=url, token=ROOT_TOKEN)
                alpha = await store.get(SecretRef(path="svc/alpha", key="api_key"))
                beta = await store.get(SecretRef(path="svc/beta", key="api_key"))
                return alpha, beta

            a, b = _run(run())
            assert a == "key-alpha"
            assert b == "key-beta"

    def test_overwrite_updates_value(self) -> None:
        with VaultContainer(root_token=ROOT_TOKEN) as container:
            url = _vault_url(container)
            _seed_secret(url, "myapp/creds", {"token": "old-token"})
            # Overwrite with new value
            _seed_secret(url, "myapp/creds", {"token": "new-token"})

            async def run() -> str:
                store = VaultSecretStore(url=url, token=ROOT_TOKEN)
                return await store.get(SecretRef(path="myapp/creds", key="token"))

            assert _run(run()) == "new-token"
