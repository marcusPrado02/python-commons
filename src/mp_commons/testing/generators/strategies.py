"""Testing generators – Hypothesis property-based testing strategies.

Requires the ``hypothesis`` package:

    pip install hypothesis
    # or
    pip install "mp-commons[testing-pbt]"
"""
from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from hypothesis.strategies import SearchStrategy  # type: ignore[import-untyped]

    from mp_commons.kernel.types import Email, EntityId, Money


def _require_hypothesis() -> Any:
    """Lazy import guard – raises a clear error when hypothesis is absent."""
    try:
        import hypothesis.strategies as st  # type: ignore[import-untyped]
        return st
    except ImportError as exc:
        raise ImportError(
            "Install 'hypothesis' to use property-based testing strategies: "
            "pip install hypothesis"
        ) from exc


_COMMON_CURRENCIES: tuple[str, ...] = (
    "BRL", "USD", "EUR", "GBP", "JPY", "CAD", "AUD", "CHF"
)


def entity_id_strategy() -> "SearchStrategy[EntityId]":
    """Hypothesis strategy that generates random :class:`EntityId` instances.

    Each drawn value is a valid, non-empty UUID-backed string identifier.

    Example::

        @given(entity_id_strategy())
        def test_entity_id_serialises(eid):
            assert str(eid)  # non-empty
    """
    from mp_commons.kernel.types.ids import EntityId

    st = _require_hypothesis()
    return st.uuids().map(lambda u: EntityId(str(u)))


def money_strategy(
    currencies: tuple[str, ...] | list[str] | None = None,
    *,
    min_amount: str | int | Decimal = "0",
    max_amount: str | int | Decimal = "9999.99",
) -> "SearchStrategy[Money]":
    """Hypothesis strategy that generates random :class:`Money` instances.

    Args:
        currencies: ISO-4217 currency codes to sample from.
            Defaults to a representative set of common currencies.
        min_amount: Inclusive minimum (non-negative, Decimal-coercible).
        max_amount: Inclusive maximum (Decimal-coercible).

    Example::

        @given(money_strategy(["BRL", "USD"]))
        def test_money_is_non_negative(m):
            assert m.amount >= 0
    """
    from mp_commons.kernel.types.money import Money

    st = _require_hypothesis()
    selected = list(currencies) if currencies is not None else list(_COMMON_CURRENCIES)
    amount_st = st.decimals(
        min_value=Decimal(str(min_amount)),
        max_value=Decimal(str(max_amount)),
        allow_nan=False,
        allow_infinity=False,
        places=2,
    )
    currency_st = st.sampled_from(selected)
    return st.builds(Money, amount=amount_st, currency=currency_st)


def email_strategy() -> "SearchStrategy[Email]":
    """Hypothesis strategy that generates valid :class:`Email` instances.

    Produces ``user@domain.tld`` strings that pass :class:`Email` validation.

    Example::

        @given(email_strategy())
        def test_email_domain_extraction(e):
            assert "." in e.domain
    """
    from mp_commons.kernel.types.email import Email

    st = _require_hypothesis()

    # Characters in each part are chosen to satisfy Email's regex
    user_st = st.text(
        alphabet="abcdefghijklmnopqrstuvwxyz0123456789",
        min_size=2,
        max_size=16,
    )
    domain_st = st.text(
        alphabet="abcdefghijklmnopqrstuvwxyz0123456789",
        min_size=2,
        max_size=10,
    )
    tld_st = st.text(
        alphabet="abcdefghijklmnopqrstuvwxyz",
        min_size=2,
        max_size=4,
    )
    return st.builds(
        lambda u, d, t: Email(f"{u}@{d}.{t}"),
        u=user_st,
        d=domain_st,
        t=tld_st,
    )


__all__ = [
    "email_strategy",
    "entity_id_strategy",
    "money_strategy",
]
