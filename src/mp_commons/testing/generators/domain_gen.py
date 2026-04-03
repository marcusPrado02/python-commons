"""Testing generators – domain object generators."""

from __future__ import annotations

import random
import string


def email_gen(domain: str = "example.com") -> str:
    """Generate a random test email address."""
    user = "".join(random.choices(string.ascii_lowercase, k=8))
    return f"{user}@{domain}"


def money_gen(min_cents: int = 1, max_cents: int = 100000) -> object:
    """Generate a random ``Money`` value object."""
    from decimal import Decimal
    import random

    from mp_commons.kernel.types import Money

    currencies = ["EUR", "USD", "GBP"]
    amount = random.randint(min_cents, max_cents)
    return Money(amount=Decimal(amount), currency=random.choice(currencies))


def slug_gen(length: int = 8) -> str:
    """Generate a random URL-safe slug."""
    chars = string.ascii_lowercase + string.digits + "-"
    slug = "".join(random.choices(chars, k=length))
    return slug.strip("-")


def domain_event_gen(event_id: str | None = None, **payload: object) -> object:
    """Generate a minimal ``DomainEvent`` for tests."""
    from datetime import UTC, datetime
    import uuid

    from mp_commons.kernel.ddd import DomainEvent

    return DomainEvent(
        event_id=event_id or str(uuid.uuid4()),
        occurred_at=datetime.now(UTC),
    )


__all__ = ["domain_event_gen", "email_gen", "money_gen", "slug_gen"]
