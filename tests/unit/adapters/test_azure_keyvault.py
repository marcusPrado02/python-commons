"""Unit tests for AzureKeyVaultSecretStore (A-08)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import mp_commons.adapters.azure_keyvault.store as _mod
from mp_commons.adapters.azure_keyvault.store import AzureKeyVaultSecretStore, _secret_name
from mp_commons.config.secrets.port import SecretRef


class TestSecretNameHelper:
    def test_combines_path_and_key(self):
        assert _secret_name("database", "password") == "database-password"

    def test_replaces_slashes_with_hyphens(self):
        assert _secret_name("app/db", "url") == "app-db-url"

    def test_replaces_underscores_with_hyphens(self):
        assert _secret_name("my_service", "api_key") == "my-service-api-key"

    def test_empty_path(self):
        assert _secret_name("", "secret") == "secret"


class TestAzureKeyVaultSecretStore:
    def _make_store(self) -> tuple[AzureKeyVaultSecretStore, MagicMock]:
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        secret = MagicMock()
        secret.value = "super-secret-value"
        mock_client.get_secret = AsyncMock(return_value=secret)

        store = AzureKeyVaultSecretStore("https://my-vault.vault.azure.net/")

        with patch.object(store, "_make_client", return_value=mock_client):
            store._patched_client = mock_client

        return store, mock_client

    @pytest.mark.asyncio
    async def test_get_returns_secret_value(self):
        store, mock_client = self._make_store()
        ref = SecretRef(path="database", key="password")

        with patch.object(store, "_make_client", return_value=mock_client):
            result = await store.get(ref)

        assert result == "super-secret-value"
        mock_client.get_secret.assert_called_once_with("database-password", version=None)

    @pytest.mark.asyncio
    async def test_get_with_version(self):
        store, mock_client = self._make_store()
        ref = SecretRef(path="db", key="pass", version="abc123")

        with patch.object(store, "_make_client", return_value=mock_client):
            await store.get(ref)

        mock_client.get_secret.assert_called_once_with("db-pass", version="abc123")

    @pytest.mark.asyncio
    async def test_get_raises_key_error_on_not_found(self):
        store, mock_client = self._make_store()
        mock_client.get_secret.side_effect = Exception("SecretNotFound")
        ref = SecretRef(path="db", key="missing")

        with patch.object(store, "_make_client", return_value=mock_client):
            with pytest.raises(KeyError, match="db-missing"):
                await store.get(ref)

    @pytest.mark.asyncio
    async def test_get_all_returns_matching_secrets(self):
        store, mock_client = self._make_store()

        props1 = MagicMock()
        props1.name = "database-host"
        props1.enabled = True
        props2 = MagicMock()
        props2.name = "database-password"
        props2.enabled = True
        props3 = MagicMock()
        props3.name = "redis-url"
        props3.enabled = True

        async def _list_props():
            for p in [props1, props2, props3]:
                yield p

        mock_client.list_properties_of_secrets = _list_props

        def _get_secret_by_name(name, **kwargs):
            secret = MagicMock()
            secret.value = f"value-of-{name}"
            return AsyncMock(return_value=secret)()

        mock_client.get_secret = MagicMock(side_effect=_get_secret_by_name)

        with patch.object(store, "_make_client", return_value=mock_client):
            result = await store.get_all("database")

        assert "database-host" in result
        assert "database-password" in result
        assert "redis-url" not in result

    @pytest.mark.asyncio
    async def test_missing_sdk_raises_on_get(self):
        store = AzureKeyVaultSecretStore("https://vault.azure.net/")
        ref = SecretRef(path="x", key="y")

        with patch.object(_mod, "_require_keyvault", side_effect=ImportError("no sdk")):
            with pytest.raises(ImportError):
                await store.get(ref)
