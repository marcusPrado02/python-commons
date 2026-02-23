"""Unit tests for Vault adapter – §34.1–34.2 (mocked, no hvac required)."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from mp_commons.adapters.vault.store import VaultSecretStore, VaultTokenRenewer
from mp_commons.config.secrets.port import SecretRef


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_hvac(kv_data: dict | None = None):
    """Return (mock_module, mock_client)."""
    kv_data = kv_data if kv_data is not None else {"my-key": "my-value"}
    mock_client = MagicMock()
    mock_client.secrets.kv.v2.read_secret_version.return_value = {
        "data": {"data": kv_data}
    }
    mock_hvac = MagicMock()
    mock_hvac.Client.return_value = mock_client
    return mock_hvac, mock_client


def _make_store(kv_data: dict | None = None, mount: str = "secret") -> tuple[VaultSecretStore, MagicMock]:
    mock_hvac, mock_client = _make_mock_hvac(kv_data)
    with patch("mp_commons.adapters.vault.store._require_hvac", return_value=mock_hvac):
        store = VaultSecretStore(url="http://vault:8200", token="tok", mount_point=mount)
    return store, mock_client


# ===========================================================================
# Import guard
# ===========================================================================

class TestVaultImportError:
    def test_raises_import_error_without_lib(self):
        with patch(
            "mp_commons.adapters.vault.store._require_hvac",
            side_effect=ImportError("mp-commons[vault]"),
        ):
            with pytest.raises(ImportError, match="vault"):
                VaultSecretStore()


# ===========================================================================
# §34.1 – VaultSecretStore
# ===========================================================================

class TestVaultSecretStoreInit:
    def test_creates_hvac_client_with_url_and_token(self):
        mock_hvac, mock_client = _make_mock_hvac()
        with patch("mp_commons.adapters.vault.store._require_hvac", return_value=mock_hvac):
            VaultSecretStore(url="http://my-vault:8200", token="s.abc123")
        mock_hvac.Client.assert_called_once_with(
            url="http://my-vault:8200", token="s.abc123"
        )

    def test_default_mount_point_is_secret(self):
        store, _ = _make_store()
        assert store._mount == "secret"

    def test_custom_mount_point(self):
        store, _ = _make_store(mount="kv")
        assert store._mount == "kv"


class TestVaultSecretStoreGet:
    def test_get_returns_value_for_key(self):
        store, mock_client = _make_store(kv_data={"db-password": "s3cr3t"})
        ref = SecretRef(path="app/db", key="db-password")
        result = asyncio.run(store.get(ref))
        assert result == "s3cr3t"

    def test_get_calls_read_secret_version_with_correct_path(self):
        store, mock_client = _make_store()
        ref = SecretRef(path="services/api", key="my-key")
        asyncio.run(store.get(ref))
        mock_client.secrets.kv.v2.read_secret_version.assert_called_once_with(
            path="services/api", mount_point="secret"
        )

    def test_get_uses_custom_mount_point(self):
        store, mock_client = _make_store(mount="kvstore")
        ref = SecretRef(path="app", key="my-key")
        asyncio.run(store.get(ref))
        call_kwargs = mock_client.secrets.kv.v2.read_secret_version.call_args.kwargs
        assert call_kwargs["mount_point"] == "kvstore"

    def test_get_raises_key_error_when_key_missing(self):
        store, _ = _make_store(kv_data={"other-key": "value"})
        ref = SecretRef(path="app", key="missing-key")
        with pytest.raises(KeyError, match="missing-key"):
            asyncio.run(store.get(ref))

    def test_get_raises_key_error_message_includes_path(self):
        store, _ = _make_store(kv_data={})
        ref = SecretRef(path="my/path", key="gone")
        with pytest.raises(KeyError, match="my/path"):
            asyncio.run(store.get(ref))


class TestVaultSecretStoreGetAll:
    def test_get_all_returns_full_dict(self):
        data = {"host": "db.internal", "port": "5432", "user": "admin"}
        store, mock_client = _make_store(kv_data=data)
        result = asyncio.run(store.get_all("infra/db"))
        assert result == data

    def test_get_all_calls_read_secret_version_with_path(self):
        store, mock_client = _make_store()
        asyncio.run(store.get_all("infra/redis"))
        mock_client.secrets.kv.v2.read_secret_version.assert_called_once_with(
            path="infra/redis", mount_point="secret"
        )

    def test_get_all_empty_dict(self):
        store, _ = _make_store(kv_data={})
        result = asyncio.run(store.get_all("empty/path"))
        assert result == {}

    def test_implements_secret_store_interface(self):
        from mp_commons.config.secrets.port import SecretStore
        assert issubclass(VaultSecretStore, SecretStore)


# ===========================================================================
# §34.2 – VaultTokenRenewer
# ===========================================================================

class TestVaultTokenRenewer:
    def _make_client(self, ttl: int = 3600):
        mock_client = MagicMock()
        mock_client.auth.token.lookup_self.return_value = {"data": {"ttl": ttl}}
        mock_client.auth.token.renew_self.return_value = {"auth": {"lease_duration": 3600}}
        return mock_client

    def test_start_creates_background_task(self):
        client = self._make_client()
        renewer = VaultTokenRenewer(client, check_interval=0.01)

        async def run():
            await renewer.start()
            assert renewer._task is not None
            assert renewer._running is True
            await renewer.stop()

        asyncio.run(run())

    def test_stop_cancels_task(self):
        client = self._make_client()
        renewer = VaultTokenRenewer(client, check_interval=1000.0)  # long interval

        async def run():
            await renewer.start()
            await renewer.stop()
            assert renewer._running is False

        asyncio.run(run())

    def test_context_manager_starts_and_stops(self):
        client = self._make_client()
        renewer = VaultTokenRenewer(client, check_interval=1000.0)

        async def run():
            async with renewer:
                assert renewer._running is True
            assert renewer._running is False

        asyncio.run(run())

    def test_renews_token_when_ttl_low(self):
        """When TTL ≤ renew_before_seconds, token is renewed."""
        client = self._make_client(ttl=60)  # low TTL
        renewer = VaultTokenRenewer(
            client,
            renew_before_seconds=300,
            check_interval=0.01,
        )

        async def run():
            await renewer.start()
            await asyncio.sleep(0.05)  # allow a couple of loop iterations
            await renewer.stop()

        asyncio.run(run())
        client.auth.token.renew_self.assert_called()

    def test_does_not_renew_when_ttl_sufficient(self):
        """When TTL > renew_before_seconds, token is NOT renewed."""
        client = self._make_client(ttl=3600)  # high TTL
        renewer = VaultTokenRenewer(
            client,
            renew_before_seconds=300,
            check_interval=0.01,
        )

        async def run():
            await renewer.start()
            await asyncio.sleep(0.05)
            await renewer.stop()

        asyncio.run(run())
        client.auth.token.renew_self.assert_not_called()

    def test_continues_loop_after_lookup_error(self):
        """lookup_self errors are swallowed; loop keeps running."""
        client = MagicMock()
        client.auth.token.lookup_self.side_effect = Exception("network error")
        renewer = VaultTokenRenewer(client, check_interval=0.01)

        async def run():
            await renewer.start()
            await asyncio.sleep(0.05)
            await renewer.stop()

        asyncio.run(run())
        # Did not crash; lookup attempted at least once
        client.auth.token.lookup_self.assert_called()

    def test_default_renew_before_seconds(self):
        client = self._make_client()
        renewer = VaultTokenRenewer(client)
        assert renewer._renew_before == 300

    def test_custom_check_interval(self):
        client = self._make_client()
        renewer = VaultTokenRenewer(client, check_interval=30.0)
        assert renewer._interval == 30.0

    def test_stop_before_start_is_safe(self):
        """Calling stop without prior start should not raise."""
        client = self._make_client()
        renewer = VaultTokenRenewer(client)
        asyncio.run(renewer.stop())  # should not raise
