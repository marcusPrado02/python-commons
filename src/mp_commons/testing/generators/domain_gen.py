"""Testing generators – domain object generators."""
from __future__ import annotations

import random
import string


def email_gen(domain: str = "example.com") -> str:
    """Generate a random test email address."""
    user = "".join(random.choices(string.ascii_lowercase, k=8))  # noqa: S311
    return f"{user}@{domain}"


def money_gen(min_cents: int = 1, max_cents: int = 100000) -> object:
    """Generate a random ``Money`` value object."""
    from mp_commons.kernel.types import Currency, Money
    currencies = [Currency.EUR, Currency.USD, Currency.GBP]
    amount = random.randint(min_cents, max_cents)  # noqa: S311
    return Money(amount=amount, currency=random.choice(currencies))  # noqa: S311


def slug_gen(length: int = 8) -> str:
    """Generate a random URL-safe slug."""
    chars = string.ascii_lowercase + string.digits + "-"
    slug = "".join(random.choices(chars, k=length))  # noqa: S311
    return slug.strip("-")


def domain_event_gen(event_type: str = "TestEvent", aggregate_id: str | None = None, **payload: object) -> object:
    """Generate a minimal ``DomainEvent`` for tests."""
    from mp_commons.kernel.ddd import DomainEvent
    from mp_commons.kernel.types import EntityId
    from datetime import UTC, datetime
    agg_id = EntityId(aggregate_id or "test-aggregate")
    return DomainEvent(
        event_type=event_type,
        aggregate_id=agg_id,
        occurred_at=datetime.now(UTC),
        payload=payload or {},
    )


__all__ = ["domain_event_gen", "email_gen", "money_gen", "slug_gen"]
