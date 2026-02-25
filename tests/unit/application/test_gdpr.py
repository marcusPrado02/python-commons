"""Unit tests for §71 – GDPR / Data Subject Rights."""
import asyncio

import pytest

from mp_commons.application.gdpr import (
    ConsentRecord,
    DataErasedEvent,
    DataPortabilityExporter,
    DataSubjectRequest,
    Erasable,
    ErasureResult,
    ErasureService,
    InMemoryConsentStore,
)


# ---------------------------------------------------------------------------
# ErasureService
# ---------------------------------------------------------------------------

class TestErasureService:
    def _make_handler(self, scope: str, success: bool = True, raises: bool = False):
        class _H:
            @property
            def scope(self):
                return scope

            async def erase(self, subject_id: str) -> ErasureResult:
                if raises:
                    raise RuntimeError("boom")
                return ErasureResult(scope=scope, success=success, detail="ok")

        return _H()

    def test_all_handlers_called(self):
        svc = ErasureService()
        svc.register(self._make_handler("orders"))
        svc.register(self._make_handler("payments"))
        event = asyncio.run(svc.erase("user-1"))
        assert isinstance(event, DataErasedEvent)
        assert len(event.results) == 2

    def test_partial_failure_recorded(self):
        svc = ErasureService()
        svc.register(self._make_handler("orders"))
        svc.register(self._make_handler("payments", raises=True))
        event = asyncio.run(svc.erase("user-1"))
        scopes = {r.scope for r in event.results}
        assert "orders" in scopes
        assert "payments" in scopes
        failed = [r for r in event.results if not r.success]
        assert len(failed) == 1

    def test_event_logged(self):
        svc = ErasureService()
        svc.register(self._make_handler("profile"))
        asyncio.run(svc.erase("user-99"))
        assert len(svc.events) == 1
        assert svc.events[0].subject_id == "user-99"


# ---------------------------------------------------------------------------
# DataPortabilityExporter
# ---------------------------------------------------------------------------

class TestDataPortabilityExporter:
    def _make_handler(self, scope: str, data: dict):
        class _H:
            @property
            def scope(self_):
                return scope

            async def export(self_, subject_id: str) -> dict:
                return data

        return _H()

    def test_merges_scopes(self):
        exporter = DataPortabilityExporter()
        exporter.register(self._make_handler("orders", {"orders": [1, 2]}))
        exporter.register(self._make_handler("profile", {"name": "Alice"}))
        result = asyncio.run(exporter.export("user-1"))
        assert "orders" in result
        assert "profile" in result


# ---------------------------------------------------------------------------
# ConsentStore
# ---------------------------------------------------------------------------

class TestConsentStore:
    def test_save_and_find(self):
        store = InMemoryConsentStore()
        record = ConsentRecord(subject_id="u1", purpose="marketing", granted=True)
        asyncio.run(store.save(record))
        found = asyncio.run(store.find("u1", "marketing"))
        assert found is not None
        assert found.granted is True

    def test_find_missing_returns_none(self):
        store = InMemoryConsentStore()
        assert asyncio.run(store.find("u1", "analytics")) is None

    def test_withdraw_consent(self):
        store = InMemoryConsentStore()
        record = ConsentRecord(subject_id="u1", purpose="analytics", granted=True)
        asyncio.run(store.save(record))
        record.withdraw()
        asyncio.run(store.save(record))
        found = asyncio.run(store.find("u1", "analytics"))
        assert found.granted is False
        assert found.withdrawn_at is not None

    def test_list_for_subject(self):
        store = InMemoryConsentStore()
        asyncio.run(store.save(ConsentRecord(subject_id="u1", purpose="marketing", granted=True)))
        asyncio.run(store.save(ConsentRecord(subject_id="u1", purpose="analytics", granted=False)))
        asyncio.run(store.save(ConsentRecord(subject_id="u2", purpose="marketing", granted=True)))
        records = asyncio.run(store.list_for_subject("u1"))
        assert len(records) == 2
