"""Unit tests for AzureBlobObjectStore (A-03)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch, AsyncMock as AM

import pytest

import mp_commons.adapters.azure_blob.object_store as _mod
from mp_commons.adapters.azure_blob.object_store import AzureBlobObjectStore


def _make_store() -> tuple[AzureBlobObjectStore, MagicMock]:
    store = AzureBlobObjectStore(
        account_url="https://myaccount.blob.core.windows.net",
        container_name="uploads",
    )
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    store._client = mock_client
    return store, mock_client


def _make_blob_client(client: MagicMock, data: bytes = b"content") -> MagicMock:
    blob = MagicMock()
    blob.__aenter__ = AsyncMock(return_value=blob)
    blob.__aexit__ = AsyncMock(return_value=False)
    blob.upload_blob = AsyncMock()
    blob.delete_blob = AsyncMock()

    stream = MagicMock()
    stream.readall = AsyncMock(return_value=data)
    blob.download_blob = AsyncMock(return_value=stream)

    client.get_blob_client.return_value = blob
    return blob


class TestAzureBlobObjectStore:
    @pytest.mark.asyncio
    async def test_put_calls_upload(self):
        store, client = _make_store()
        blob = _make_blob_client(client)

        await store.put("folder/file.txt", b"hello", "text/plain")
        blob.upload_blob.assert_called_once()
        call_args = blob.upload_blob.call_args
        assert call_args[0][0] == b"hello"

    @pytest.mark.asyncio
    async def test_get_returns_bytes(self):
        store, client = _make_store()
        _make_blob_client(client, b"data-here")

        result = await store.get("folder/file.txt")
        assert result == b"data-here"

    @pytest.mark.asyncio
    async def test_get_raises_key_error_on_not_found(self):
        store, client = _make_store()
        blob = _make_blob_client(client)
        blob.download_blob.side_effect = Exception("BlobNotFound")

        with pytest.raises(KeyError):
            await store.get("missing.txt")

    @pytest.mark.asyncio
    async def test_delete_calls_delete_blob(self):
        store, client = _make_store()
        blob = _make_blob_client(client)

        await store.delete("folder/file.txt")
        blob.delete_blob.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_ignores_not_found(self):
        store, client = _make_store()
        blob = _make_blob_client(client)
        blob.delete_blob.side_effect = Exception("BlobNotFound")

        await store.delete("missing.txt")  # must not raise

    @pytest.mark.asyncio
    async def test_list_returns_blob_names(self):
        store, client = _make_store()
        container_client = MagicMock()

        blob1 = MagicMock()
        blob1.name = "uploads/a.txt"
        blob2 = MagicMock()
        blob2.name = "uploads/b.txt"

        async def _list_blobs(**kwargs):
            for b in [blob1, blob2]:
                yield b

        container_client.list_blobs = _list_blobs
        client.get_container_client.return_value = container_client

        names = await store.list("uploads/")
        assert "uploads/a.txt" in names
        assert "uploads/b.txt" in names

    @pytest.mark.asyncio
    async def test_missing_sdk_raises(self):
        with patch.object(_mod, "_require_blob", side_effect=ImportError("no sdk")):
            store = AzureBlobObjectStore("https://x.blob.core.windows.net", "c")
            with pytest.raises(ImportError):
                await store.__aenter__()
