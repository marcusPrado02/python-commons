"""Unit tests for test data generators (§38)."""

from __future__ import annotations

import re
import uuid

from mp_commons.testing.generators import (
    correlation_id_gen,
    domain_event_gen,
    email_gen,
    money_gen,
    slug_gen,
    ulid_gen,
)
from mp_commons.kernel.ddd import DomainEvent
from mp_commons.kernel.types import Money


# ---------------------------------------------------------------------------
# §38.1  ulid_gen / correlation_id_gen
# ---------------------------------------------------------------------------


class TestIdGenerators:
    def test_ulid_gen_length(self) -> None:
        assert len(ulid_gen()) == 26

    def test_ulid_gen_alphanumeric_uppercase(self) -> None:
        result = ulid_gen()
        assert result.isupper() or result.isalnum()
        assert re.fullmatch(r"[A-Z0-9]{26}", result)

    def test_ulid_gen_unique(self) -> None:
        ids = {ulid_gen() for _ in range(100)}
        assert len(ids) > 90  # very high probability of uniqueness

    def test_correlation_id_gen_is_uuid4(self) -> None:
        cid = correlation_id_gen()
        parsed = uuid.UUID(cid)
        assert parsed.version == 4

    def test_correlation_id_gen_unique(self) -> None:
        ids = {correlation_id_gen() for _ in range(20)}
        assert len(ids) == 20


# ---------------------------------------------------------------------------
# §38.2  email_gen / slug_gen
# ---------------------------------------------------------------------------


class TestDomainGenerators:
    def test_email_gen_format(self) -> None:
        email = email_gen()
        assert "@" in email
        assert email.endswith("@example.com")

    def test_email_gen_custom_domain(self) -> None:
        email = email_gen(domain="acme.io")
        assert email.endswith("@acme.io")

    def test_email_gen_unique(self) -> None:
        emails = {email_gen() for _ in range(50)}
        assert len(emails) > 40

    def test_slug_gen_length(self) -> None:
        slug = slug_gen(length=10)
        assert 1 <= len(slug) <= 10

    def test_slug_gen_chars(self) -> None:
        for _ in range(20):
            slug = slug_gen()
            assert re.fullmatch(r"[a-z0-9\-]+", slug), f"invalid slug: {slug}"

    def test_slug_gen_no_leading_trailing_hyphen(self) -> None:
        for _ in range(50):
            slug = slug_gen()
            assert not slug.startswith("-")
            assert not slug.endswith("-")

    def test_slug_gen_default_length(self) -> None:
        slug = slug_gen()
        assert 1 <= len(slug) <= 8


# ---------------------------------------------------------------------------
# §38.2  money_gen
# ---------------------------------------------------------------------------


class TestMoneyGenerator:
    def test_money_gen_returns_money(self) -> None:
        m = money_gen()
        assert isinstance(m, Money)

    def test_money_gen_positive_amount(self) -> None:
        m = money_gen()
        assert m.amount >= 1  # type: ignore[attr-defined]

    def test_money_gen_known_currency(self) -> None:
        currencies = {"EUR", "USD", "GBP"}
        for _ in range(20):
            m = money_gen()
            assert m.currency in currencies  # type: ignore[attr-defined]

    def test_money_gen_range(self) -> None:
        for _ in range(20):
            m = money_gen(min_cents=500, max_cents=1000)
            assert 500 <= m.amount <= 1000  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# §38  domain_event_gen
# ---------------------------------------------------------------------------


class TestDomainEventGenerator:
    def test_returns_domain_event(self) -> None:
        e = domain_event_gen()
        assert isinstance(e, DomainEvent)

    def test_has_event_id(self) -> None:
        e = domain_event_gen()
        assert e.event_id is not None  # type: ignore[attr-defined]

    def test_custom_event_id(self) -> None:
        e = domain_event_gen(event_id="fixed-id-123")
        assert e.event_id == "fixed-id-123"  # type: ignore[attr-defined]

    def test_has_occurred_at(self) -> None:
        e = domain_event_gen()
        assert e.occurred_at is not None  # type: ignore[attr-defined]

    def test_unique_event_ids_by_default(self) -> None:
        events = [domain_event_gen() for _ in range(10)]
        ids = {e.event_id for e in events}  # type: ignore[attr-defined]
        assert len(ids) == 10
