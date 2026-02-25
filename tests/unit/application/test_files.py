"""Unit tests for §65 Application — File Upload."""
from __future__ import annotations

import asyncio

import hashlib

import pytest

from mp_commons.application.files import (
    AntivirusScanner,
    FileUploadedEvent,
    FileUploadService,
    FileValidationError,
    FileValidator,
    InMemoryObjectStore,
    ObjectStore,
    ScanResult,
    UploadedFile,
    ValidationResult,
)


# ---------------------------------------------------------------------------
# UploadedFile
# ---------------------------------------------------------------------------
class TestUploadedFile:
    def test_from_bytes_computes_checksum(self):
        data = b"Hello, World!"
        f = UploadedFile.from_bytes("hello.txt", "text/plain", data)
        expected = hashlib.sha256(data).hexdigest()
        assert f.checksum_sha256 == expected
        assert f.size_bytes == len(data)
        assert f.filename == "hello.txt"
        assert f.content_type == "text/plain"

    def test_post_init_computes_checksum_when_empty(self):
        data = b"abc"
        f = UploadedFile(filename="a.txt", content_type="text/plain", size_bytes=3, data=data)
        assert f.checksum_sha256 == hashlib.sha256(data).hexdigest()

    def test_explicit_checksum_not_overwritten(self):
        # If checksum_sha256 is pre-filled, __post_init__ should leave it
        data = b"abc"
        f = UploadedFile(
            filename="a.txt",
            content_type="text/plain",
            size_bytes=3,
            data=data,
            checksum_sha256="precomputed",
        )
        # __post_init__ only fills when checksum_sha256 == ""
        assert f.checksum_sha256 == "precomputed"


# ---------------------------------------------------------------------------
# FileValidator
# ---------------------------------------------------------------------------
class TestFileValidator:
    def test_valid_file_passes(self):
        v = FileValidator(max_size_bytes=1024, allowed_content_types={"image/png"})
        f = UploadedFile.from_bytes("img.png", "image/png", b"x" * 100)
        result = v.validate(f)
        assert result.valid is True
        assert result.errors == ()

    def test_oversized_file_fails(self):
        v = FileValidator(max_size_bytes=10)
        f = UploadedFile.from_bytes("big.txt", "text/plain", b"x" * 100)
        result = v.validate(f)
        assert result.valid is False
        assert any("size" in e.lower() for e in result.errors)

    def test_disallowed_content_type_fails(self):
        v = FileValidator(allowed_content_types={"image/png"})
        f = UploadedFile.from_bytes("doc.pdf", "application/pdf", b"%PDF")
        result = v.validate(f)
        assert result.valid is False
        assert any("application/pdf" in e for e in result.errors)

    def test_multiple_errors_accumulate(self):
        v = FileValidator(max_size_bytes=5, allowed_content_types={"image/png"})
        f = UploadedFile.from_bytes("doc.pdf", "application/pdf", b"x" * 100)
        result = v.validate(f)
        assert len(result.errors) == 2

    def test_validate_or_raise_raises_on_invalid(self):
        v = FileValidator(max_size_bytes=5)
        f = UploadedFile.from_bytes("big.bin", "application/octet-stream", b"x" * 100)
        with pytest.raises(FileValidationError) as exc_info:
            v.validate_or_raise(f)
        assert "size" in str(exc_info.value).lower()

    def test_validate_or_raise_passes_for_valid(self):
        v = FileValidator(max_size_bytes=1000, allowed_content_types={"text/plain"})
        f = UploadedFile.from_bytes("ok.txt", "text/plain", b"hello")
        v.validate_or_raise(f)  # must not raise

    def test_no_constraints_always_valid(self):
        v = FileValidator()
        f = UploadedFile.from_bytes("any.bin", "application/octet-stream", b"x" * 99999)
        assert v.validate(f).valid is True


# ---------------------------------------------------------------------------
# ValidationResult
# ---------------------------------------------------------------------------
class TestValidationResult:
    def test_ok(self):
        r = ValidationResult.ok()
        assert r.valid is True
        assert r.errors == ()

    def test_fail(self):
        r = ValidationResult.fail("too big", "wrong type")
        assert r.valid is False
        assert "too big" in r.errors


# ---------------------------------------------------------------------------
# InMemoryObjectStore
# ---------------------------------------------------------------------------
class TestInMemoryObjectStore:
    def test_put_returns_url(self):
        async def _run():
            store = InMemoryObjectStore("https://cdn.example.com")
            url = await store.put("images/cat.png", b"\x89PNG", "image/png")
            assert url == "https://cdn.example.com/images/cat.png"
        asyncio.run(_run())
    def test_exists_after_put(self):
        async def _run():
            store = InMemoryObjectStore()
            await store.put("file.txt", b"content", "text/plain")
            assert await store.exists("file.txt") is True
            assert await store.exists("missing.txt") is False
        asyncio.run(_run())
    def test_delete_removes_file(self):
        async def _run():
            store = InMemoryObjectStore()
            await store.put("tmp.bin", b"data", "application/octet-stream")
            await store.delete("tmp.bin")
            assert await store.exists("tmp.bin") is False
        asyncio.run(_run())
    def test_get_returns_data(self):
        async def _run():
            store = InMemoryObjectStore()
            await store.put("f.bin", b"hello", "application/octet-stream")
            assert store.get("f.bin") == b"hello"
        asyncio.run(_run())
    def test_is_protocol_compatible(self):
        store = InMemoryObjectStore()
        assert isinstance(store, ObjectStore)


# ---------------------------------------------------------------------------
# FileUploadService
# ---------------------------------------------------------------------------
class TestFileUploadService:
    def test_upload_stores_file_and_emits_event(self):
        async def _run():
            store = InMemoryObjectStore()
            svc = FileUploadService(store)
            f = UploadedFile.from_bytes("report.pdf", "application/pdf", b"%PDF-1.4")
            url = await svc.upload(f, "docs/report.pdf")

            assert url.endswith("docs/report.pdf")
            assert await store.exists("docs/report.pdf")
            assert len(svc.events) == 1
            event = svc.events[0]
            assert isinstance(event, FileUploadedEvent)
            assert event.filename == "report.pdf"
            assert event.destination_key == "docs/report.pdf"
        asyncio.run(_run())
    def test_upload_raises_on_validation_failure(self):
        async def _run():
            store = InMemoryObjectStore()
            validator = FileValidator(max_size_bytes=4)
            svc = FileUploadService(store, validator=validator)
            f = UploadedFile.from_bytes("large.bin", "application/octet-stream", b"x" * 100)
            with pytest.raises(FileValidationError):
                await svc.upload(f, "large.bin")
            assert not await store.exists("large.bin")
            assert len(svc.events) == 0
        asyncio.run(_run())
    def test_upload_without_validator_accepts_anything(self):
        async def _run():
            store = InMemoryObjectStore()
            svc = FileUploadService(store)
            f = UploadedFile.from_bytes("huge.bin", "application/octet-stream", b"x" * 10_000)
            url = await svc.upload(f, "huge.bin")
            assert url.endswith("huge.bin")
        asyncio.run(_run())
    def test_multiple_uploads_accumulate_events(self):
        async def _run():
            store = InMemoryObjectStore()
            svc = FileUploadService(store)
            for i in range(3):
                f = UploadedFile.from_bytes(f"f{i}.txt", "text/plain", b"data")
                await svc.upload(f, f"uploads/f{i}.txt")
            assert len(svc.events) == 3
        asyncio.run(_run())
# ---------------------------------------------------------------------------
# ScanResult
# ---------------------------------------------------------------------------
class TestScanResult:
    def test_clean_scan(self):
        r = ScanResult(clean=True)
        assert r.clean is True
        assert r.threat_name is None

    def test_infected_scan(self):
        r = ScanResult(clean=False, threat_name="EICAR", detail="found in header")
        assert r.clean is False
        assert r.threat_name == "EICAR"
