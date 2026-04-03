"""Integration tests for S3 adapter using MinIO (§49.6 / B-04).

Uses testcontainers MinioContainer as a local S3-compatible endpoint.
Run with: pytest tests/integration/test_s3.py -m integration -v

Requires Docker.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from testcontainers.minio import MinioContainer

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _run(coro: Any) -> Any:  # type: ignore[no-untyped-def]
    return asyncio.run(coro)


_BUCKET = "test-bucket"
_ACCESS_KEY = "minioadmin"
_SECRET_KEY = "minioadmin"


@pytest.fixture(scope="module")
def s3_config() -> dict:  # type: ignore[return]
    with MinioContainer(
        image="minio/minio:latest",
        access_key=_ACCESS_KEY,
        secret_key=_SECRET_KEY,
    ) as minio:
        host = minio.get_container_host_ip()
        port = minio.get_exposed_port(9000)
        endpoint = f"http://{host}:{port}"

        # Create the test bucket via boto3 (synchronous setup)
        import boto3

        s3 = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=_ACCESS_KEY,
            aws_secret_access_key=_SECRET_KEY,
            region_name="us-east-1",
        )
        s3.create_bucket(Bucket=_BUCKET)

        yield {
            "endpoint_url": endpoint,
            "bucket": _BUCKET,
            "access_key_id": _ACCESS_KEY,
            "secret_access_key": _SECRET_KEY,
            "region_name": "us-east-1",
        }


# ---------------------------------------------------------------------------
# §49.6 — S3ObjectStore
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestS3ObjectStoreIntegration:
    """Full CRUD tests against a MinIO container."""

    def _make_store(self, cfg: dict) -> Any:
        from mp_commons.adapters.s3 import S3ObjectStore

        return S3ObjectStore(
            cfg["bucket"],
            region=cfg["region_name"],
            endpoint_url=cfg["endpoint_url"],
            aws_access_key_id=cfg["access_key_id"],
            aws_secret_access_key=cfg["secret_access_key"],
        )

    def _make_presign(self, cfg: dict) -> Any:
        from mp_commons.adapters.s3.object_store import S3PresignedUrlGenerator

        return S3PresignedUrlGenerator(
            cfg["bucket"],
            region=cfg["region_name"],
            endpoint_url=cfg["endpoint_url"],
            aws_access_key_id=cfg["access_key_id"],
            aws_secret_access_key=cfg["secret_access_key"],
        )

    def test_put_and_get_round_trip(self, s3_config: dict) -> None:
        store = self._make_store(s3_config)

        async def _run_test() -> None:
            await store.put("folder/file.txt", b"hello world", "text/plain")
            data = await store.get("folder/file.txt")
            assert data == b"hello world"

        _run(_run_test())

    def test_delete_removes_object(self, s3_config: dict) -> None:
        store = self._make_store(s3_config)

        async def _run_test() -> None:
            await store.put("to-delete.bin", b"data", "application/octet-stream")
            await store.delete("to-delete.bin")
            with pytest.raises(KeyError):
                await store.get("to-delete.bin")

        _run(_run_test())

    def test_get_missing_raises_key_error(self, s3_config: dict) -> None:
        store = self._make_store(s3_config)

        async def _run_test() -> None:
            with pytest.raises(KeyError):
                await store.get("does-not-exist.txt")

        _run(_run_test())

    def test_list_keys_returns_uploaded_objects(self, s3_config: dict) -> None:
        store = self._make_store(s3_config)

        async def _run_test() -> None:
            await store.put("prefix/a.txt", b"a", "text/plain")
            await store.put("prefix/b.txt", b"b", "text/plain")
            keys = await store.list_keys("prefix/")
            assert "prefix/a.txt" in keys
            assert "prefix/b.txt" in keys

        _run(_run_test())

    def test_presigned_url_accessible_via_http_get(self, s3_config: dict) -> None:
        import urllib.request

        store = self._make_store(s3_config)
        presign = self._make_presign(s3_config)

        async def _get_url() -> str:
            await store.put("signed/obj.bin", b"signed-content", "application/octet-stream")
            return await presign.presign_get("signed/obj.bin", expires_in=300)

        url = _run(_get_url())
        assert url.startswith("http")
        with urllib.request.urlopen(url, timeout=10) as resp:
            body = resp.read()
        assert body == b"signed-content"
