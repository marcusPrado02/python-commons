"""Unit tests for GCSObjectStore (A-04)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

import mp_commons.adapters.gcs.object_store as _mod
from mp_commons.adapters.gcs.object_store import GCSObjectStore


def _make_store() -> tuple[GCSObjectStore, MagicMock, MagicMock]:
    store = GCSObjectStore(bucket_name="my-bucket", project="my-proj")
    mock_client = MagicMock()
    mock_bucket = MagicMock()
    mock_client.bucket.return_value = mock_bucket
    store._client = mock_client
    store._bucket = mock_bucket
    return store, mock_client, mock_bucket


def _make_blob(bucket: MagicMock, data: bytes = b"content") -> MagicMock:
    blob = MagicMock()
    blob.upload_from_string = MagicMock()
    blob.download_as_bytes = MagicMock(return_value=data)
    blob.delete = MagicMock()
    blob.generate_signed_url = MagicMock(return_value="https://signed.url/file")
    bucket.blob.return_value = blob
    return blob


class TestGCSObjectStore:
    @pytest.mark.asyncio
    async def test_put_calls_upload(self):
        store, _, bucket = _make_store()
        blob = _make_blob(bucket)
        await store.put("folder/file.txt", b"data", "text/plain")
        blob.upload_from_string.assert_called_once_with(b"data", content_type="text/plain")

    @pytest.mark.asyncio
    async def test_get_returns_bytes(self):
        store, _, bucket = _make_store()
        _make_blob(bucket, b"file-content")
        result = await store.get("folder/file.txt")
        assert result == b"file-content"

    @pytest.mark.asyncio
    async def test_get_raises_key_error_on_not_found(self):
        store, _, bucket = _make_store()
        blob = _make_blob(bucket)
        blob.download_as_bytes.side_effect = Exception("No such object: my-bucket/missing.txt")
        with pytest.raises(KeyError):
            await store.get("missing.txt")

    @pytest.mark.asyncio
    async def test_delete_calls_blob_delete(self):
        store, _, bucket = _make_store()
        blob = _make_blob(bucket)
        await store.delete("folder/file.txt")
        blob.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_ignores_not_found(self):
        store, _, bucket = _make_store()
        blob = _make_blob(bucket)
        blob.delete.side_effect = Exception("No such object: my-bucket/missing.txt")
        await store.delete("missing.txt")  # must not raise

    @pytest.mark.asyncio
    async def test_list_returns_blob_names(self):
        store, client, _ = _make_store()
        b1 = MagicMock()
        b1.name = "uploads/a.txt"
        b2 = MagicMock()
        b2.name = "uploads/b.txt"
        client.list_blobs.return_value = [b1, b2]

        names = await store.list("uploads/")
        assert "uploads/a.txt" in names
        assert "uploads/b.txt" in names

    @pytest.mark.asyncio
    async def test_presigned_url_returns_url(self):
        store, _, bucket = _make_store()
        _make_blob(bucket)
        url = await store.presigned_url("file.txt", expires_in=600)
        assert url == "https://signed.url/file"

    @pytest.mark.asyncio
    async def test_missing_sdk_raises(self):
        with patch.object(_mod, "_require_storage", side_effect=ImportError("no gcs")):
            store = GCSObjectStore(bucket_name="b")
            with pytest.raises(ImportError):
                await store.__aenter__()
