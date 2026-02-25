"""Unit tests for §68 Application — Webhooks."""
from __future__ import annotations

import asyncio

import pytest

from mp_commons.application.webhooks import (
    InMemoryWebhookEndpointStore,
    WebhookDeliveryRecord,
    WebhookEndpoint,
    WebhookEndpointStore,
    WebhookSigner,
)


# ---------------------------------------------------------------------------
# WebhookEndpoint
# ---------------------------------------------------------------------------
class TestWebhookEndpoint:
    def test_matches_subscribed_event(self):
        ep = WebhookEndpoint(
            url="https://ep.example.com",
            secret="s3cr3t",
            events=frozenset({"order.created", "order.shipped"}),
            id="ep1",
        )
        assert ep.matches("order.created") is True
        assert ep.matches("order.shipped") is True

    def test_does_not_match_unsubscribed_event(self):
        ep = WebhookEndpoint(
            url="https://ep.example.com",
            secret="s3cr3t",
            events=frozenset({"order.created"}),
            id="ep1",
        )
        assert ep.matches("payment.failed") is False

    def test_empty_events_matches_all(self):
        ep = WebhookEndpoint(
            url="https://ep.example.com",
            secret="s3cr3t",
            events=frozenset(),
            id="ep1",
        )
        assert ep.matches("anything") is True
        assert ep.matches("other.event") is True

    def test_disabled_endpoint_never_matches(self):
        ep = WebhookEndpoint(
            url="https://ep.example.com",
            secret="s3cr3t",
            events=frozenset({"order.created"}),
            enabled=False,
            id="ep1",
        )
        assert ep.matches("order.created") is False

    def test_frozen(self):
        ep = WebhookEndpoint(url="https://x.com", secret="abc", id="e1")
        with pytest.raises(Exception):
            ep.url = "https://other.com"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# WebhookSigner
# ---------------------------------------------------------------------------
class TestWebhookSigner:
    def test_sign_returns_sha256_prefix(self):
        sig = WebhookSigner.sign(b"hello", "secret")
        assert sig.startswith("sha256=")

    def test_verify_accepts_correct_signature(self):
        payload = b'{"event":"order.created","data":{}}'
        secret = "my-webhook-secret"
        sig = WebhookSigner.sign(payload, secret)
        assert WebhookSigner.verify(payload, secret, sig) is True

    def test_verify_rejects_tampered_payload(self):
        payload = b'{"event":"order.created","data":{}}'
        secret = "my-webhook-secret"
        sig = WebhookSigner.sign(payload, secret)
        tampered = b'{"event":"order.created","data":{"evil":true}}'
        assert WebhookSigner.verify(tampered, secret, sig) is False

    def test_verify_rejects_wrong_secret(self):
        payload = b"data"
        sig = WebhookSigner.sign(payload, "correct-secret")
        assert WebhookSigner.verify(payload, "wrong-secret", sig) is False

    def test_different_payloads_produce_different_signatures(self):
        s1 = WebhookSigner.sign(b"payload1", "secret")
        s2 = WebhookSigner.sign(b"payload2", "secret")
        assert s1 != s2

    def test_deterministic_for_same_input(self):
        s1 = WebhookSigner.sign(b"payload", "secret")
        s2 = WebhookSigner.sign(b"payload", "secret")
        assert s1 == s2


# ---------------------------------------------------------------------------
# InMemoryWebhookEndpointStore
# ---------------------------------------------------------------------------
class TestInMemoryWebhookEndpointStore:
    def test_save_and_find_by_event(self):
        async def _run():
            store = InMemoryWebhookEndpointStore()
            ep = WebhookEndpoint(
                url="https://hook.example.com",
                secret="s",
                events=frozenset({"order.created"}),
                id="ep1",
            )
            await store.save(ep)
            found = await store.find_by_event("order.created")
            assert len(found) == 1
            assert found[0].id == "ep1"
        asyncio.run(_run())
    def test_find_by_event_excludes_non_matching(self):
        async def _run():
            store = InMemoryWebhookEndpointStore()
            ep = WebhookEndpoint(
                url="https://hook.example.com",
                secret="s",
                events=frozenset({"order.created"}),
                id="ep1",
            )
            await store.save(ep)
            found = await store.find_by_event("payment.failed")
            assert found == []
        asyncio.run(_run())
    def test_find_by_event_returns_all_subscribers(self):
        async def _run():
            store = InMemoryWebhookEndpointStore()
            for i in range(3):
                ep = WebhookEndpoint(
                    url=f"https://hook{i}.example.com",
                    secret="s",
                    events=frozenset({"order.created"}),
                    id=f"ep{i}",
                )
                await store.save(ep)
            found = await store.find_by_event("order.created")
            assert len(found) == 3
        asyncio.run(_run())
    def test_remove_endpoint(self):
        async def _run():
            store = InMemoryWebhookEndpointStore()
            ep = WebhookEndpoint(url="https://h.com", secret="s", events=frozenset({"x"}), id="ep1")
            await store.save(ep)
            await store.remove("ep1")
            found = await store.find_by_event("x")
            assert found == []
        asyncio.run(_run())
    def test_remove_nonexistent_is_noop(self):
        async def _run():
            store = InMemoryWebhookEndpointStore()
            await store.remove("ghost")  # must not raise
        asyncio.run(_run())
    def test_disabled_endpoint_not_returned(self):
        async def _run():
            store = InMemoryWebhookEndpointStore()
            ep = WebhookEndpoint(
                url="https://h.com",
                secret="s",
                events=frozenset({"order.created"}),
                enabled=False,
                id="ep1",
            )
            await store.save(ep)
            found = await store.find_by_event("order.created")
            assert found == []
        asyncio.run(_run())
    def test_is_protocol_compatible(self):
        store = InMemoryWebhookEndpointStore()
        assert isinstance(store, WebhookEndpointStore)


# ---------------------------------------------------------------------------
# WebhookDeliveryRecord
# ---------------------------------------------------------------------------
class TestWebhookDeliveryRecord:
    def test_default_values(self):
        rec = WebhookDeliveryRecord(endpoint_id="ep1", event_type="order.created")
        assert rec.http_status is None
        assert rec.attempts == 0
        assert rec.duration_ms == 0.0
        assert rec.last_error is None

    def test_set_fields(self):
        rec = WebhookDeliveryRecord(
            endpoint_id="ep1",
            event_type="payment.failed",
            http_status=200,
            duration_ms=42.5,
            attempts=1,
        )
        assert rec.http_status == 200
        assert rec.duration_ms == 42.5
