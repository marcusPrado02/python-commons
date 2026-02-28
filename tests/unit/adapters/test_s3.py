"""Unit tests for the S3 object-store adapter (§49)."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mp_commons.adapters.s3.object_store import InMemoryObjectStore, S3ObjectStore, S3PresignedUrlGenerator


# ---------------------------------------------------------------------------
# InMemoryObjectStore
# ---------------------------------------------------------------------------


def test_in_memory_put_get_round_trip():
    store = InMemoryObjectStore()

    async def run():
        await store.put("key1", b"hello")
        result = await store.get("key1")
        assert result == b"hello"

    asyncio.run(run())


def test_in_memory_delete_removes_key():
    store = InMemoryObjectStore()

    async def run():
        await store.put("k", b"data")
        await store.delete("k")
        assert not await store.exists("k")

    asyncio.run(run())


def test_in_memory_get_raises_key_error_for_missing():
    store = InMemoryObjectStore()

    async def run():
        await store.get("missing")

    with pytest.raises(KeyError):
        asyncio.run(run())


def test_in_memory_exists_returns_bool():
    store = InMemoryObjectStore()

    async def run():
        assert not await store.exists("x")
        await store.put("x", b"1")
        assert await store.exists("x")

    asyncio.run(run())


def test_in_memory_list_keys_with_prefix():
    store = InMemoryObjectStore()

    async def run():
        await store.put("images/a.png", b"a")
        await store.put("images/b.png", b"b")
        await store.put("docs/c.pdf", b"c")
        keys = await store.list_keys("images/")
        assert sorted(keys) == ["images/a.png", "images/b.png"]

    asyncio.run(run())


def test_in_memory_list_keys_all():
    store = InMemoryObjectStore()

    async def run():
        await store.put("a", b"1")
        await store.put("b", b"2")
        return await store.list_keys()

    result = asyncio.run(run())
    assert sorted(result) == ["a", "b"]


def test_in_memory_delete_no_op_on_missing():
    store = InMemoryObjectStore()

    async def run():
        await store.delete("nonexistent")  # should not raise

    asyncio.run(run())


# ---------------------------------------------------------------------------
# S3ObjectStore (mocked aiobotocore)
# ---------------------------------------------------------------------------


def _mock_s3_client(**method_returns):
    """Build a mock async S3 client context manager."""
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    for method, retval in method_returns.items():
        setattr(mock_client, method, AsyncMock(return_value=retval))
    return mock_client


def test_s3_put_calls_put_object():
    mock_client = _mock_s3_client(put_object=None)
    store = S3ObjectStore.__new__(S3ObjectStore)
    store._bucket = "my-bucket"
    store._region = "us-east-1"
    store._endpoint_url = None
    store._session_kwargs = {}
    store._client_context = MagicMock(return_value=mock_client)

    asyncio.run(store.put("key", b"data", "text/plain"))
    mock_client.put_object.assert_called_once_with(
        Bucket="my-bucket", Key="key", Body=b"data", ContentType="text/plain"
    )


def test_s3_get_returns_bytes():
    body_mock = MagicMock()
    body_mock.read = AsyncMock(return_value=b"content")
    mock_client = _mock_s3_client(get_object={"Body": body_mock})
    store = S3ObjectStore.__new__(S3ObjectStore)
    store._bucket = "my-bucket"
    store._region = "us-east-1"
    store._endpoint_url = None
    store._session_kwargs = {}
    store._client_context = MagicMock(return_value=mock_client)

    result = asyncio.run(store.get("key"))
    assert result == b"content"


def test_s3_get_raises_key_error_on_no_such_key():
    class _NoSuchKey(Exception):
        pass

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get_object = AsyncMock(side_effect=_NoSuchKey("NoSuchKey"))
    store = S3ObjectStore.__new__(S3ObjectStore)
    store._bucket = "b"
    store._region = "us-east-1"
    store._endpoint_url = None
    store._session_kwargs = {}
    store._client_context = MagicMock(return_value=mock_client)

    with pytest.raises(KeyError):
        asyncio.run(store.get("missing"))


def test_s3_exists_true_on_head_success():
    mock_client = _mock_s3_client(head_object={"ContentLength": 10})
    store = S3ObjectStore.__new__(S3ObjectStore)
    store._bucket = "b"
    store._region = "us-east-1"
    store._endpoint_url = None
    store._session_kwargs = {}
    store._client_context = MagicMock(return_value=mock_client)

    result = asyncio.run(store.exists("key"))
    assert result is True


def test_s3_exists_false_on_exception():
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.head_object = AsyncMock(side_effect=Exception("404"))
    store = S3ObjectStore.__new__(S3ObjectStore)
    store._bucket = "b"
    store._region = "us-east-1"
    store._endpoint_url = None
    store._session_kwargs = {}
    store._client_context = MagicMock(return_value=mock_client)

    result = asyncio.run(store.exists("missing"))
    assert result is False


def test_s3_list_keys():
    mock_client = _mock_s3_client(
        list_objects_v2={"Contents": [{"Key": "a/1"}, {"Key": "a/2"}]}
    )
    store = S3ObjectStore.__new__(S3ObjectStore)
    store._bucket = "b"
    store._region = "us-east-1"
    store._endpoint_url = None
    store._session_kwargs = {}
    store._client_context = MagicMock(return_value=mock_client)

    result = asyncio.run(store.list_keys("a/"))
    assert sorted(result) == ["a/1", "a/2"]


# ---------------------------------------------------------------------------
# S3PresignedUrlGenerator
# ---------------------------------------------------------------------------


def test_presign_get_returns_url():
    mock_client = _mock_s3_client(
        generate_presigned_url="https://s3.example.com/bucket/key?sig=abc"
    )
    gen = S3PresignedUrlGenerator.__new__(S3PresignedUrlGenerator)
    gen._bucket = "b"
    gen._region = "us-east-1"
    gen._endpoint_url = None
    gen._session_kwargs = {}
    gen._client_context = MagicMock(return_value=mock_client)

    url = asyncio.run(gen.presign_get("key", expires_in=300))
    assert "https" in url
    mock_client.generate_presigned_url.assert_called_once_with(
        "get_object",
        Params={"Bucket": "b", "Key": "key"},
        ExpiresIn=300,
    )


def test_presign_put_returns_url():
    mock_client = _mock_s3_client(
        generate_presigned_url="https://s3.example.com/bucket/key?sig=xyz"
    )
    gen = S3PresignedUrlGenerator.__new__(S3PresignedUrlGenerator)
    gen._bucket = "b"
    gen._region = "us-east-1"
    gen._endpoint_url = None
    gen._session_kwargs = {}
    gen._client_context = MagicMock(return_value=mock_client)

    url = asyncio.run(gen.presign_put("key", expires_in=600, content_type="image/jpeg"))
    assert "https" in url
    mock_client.generate_presigned_url.assert_called_once_with(
        "put_object",
        Params={"Bucket": "b", "Key": "key", "ContentType": "image/jpeg"},
        ExpiresIn=600,
    )
