"""Hypothesis property tests for Money (T-06)."""

from __future__ import annotations

from decimal import Decimal

from hypothesis import assume, given
from hypothesis import strategies as st
import pytest

from mp_commons.kernel.errors.domain import ValidationError
from mp_commons.kernel.types.money import Money

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

CURRENCIES = st.sampled_from(["USD", "EUR", "BRL", "GBP", "JPY", "CHF"])

AMOUNTS = st.decimals(
    min_value=Decimal("0"),
    max_value=Decimal("1_000_000"),
    allow_nan=False,
    allow_infinity=False,
    places=2,
)

POSITIVE_AMOUNTS = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("1_000_000"),
    allow_nan=False,
    allow_infinity=False,
    places=2,
)


def money(amount_st=AMOUNTS, currency_st=CURRENCIES) -> st.SearchStrategy:
    return st.builds(Money, amount=amount_st, currency=currency_st)


# ---------------------------------------------------------------------------
# Commutativity of add
# ---------------------------------------------------------------------------


@given(money(), money())
def test_add_commutativity(a: Money, b: Money) -> None:
    """a + b == b + a (when same currency)."""
    assume(a.currency == b.currency)
    assert a + b == b + a


@given(money(), money(), money())
def test_add_associativity(a: Money, b: Money, c: Money) -> None:
    """(a + b) + c == a + (b + c)."""
    assume(a.currency == b.currency == c.currency)
    assert (a + b) + c == a + (b + c)


@given(money())
def test_add_zero_identity(m: Money) -> None:
    """m + 0 == m."""
    zero = Money(Decimal("0"), m.currency)
    assert m + zero == m
    assert zero + m == m


# ---------------------------------------------------------------------------
# Currency mismatch always raises
# ---------------------------------------------------------------------------


@given(money(), money())
def test_add_different_currencies_raises(a: Money, b: Money) -> None:
    assume(a.currency != b.currency)
    with pytest.raises(ValidationError, match="Currency mismatch"):
        _ = a + b


@given(money(), money())
def test_sub_different_currencies_raises(a: Money, b: Money) -> None:
    assume(a.currency != b.currency)
    with pytest.raises(ValidationError, match="Currency mismatch"):
        _ = a - b


# ---------------------------------------------------------------------------
# Multiply never returns negative for non-negative inputs
# ---------------------------------------------------------------------------


@given(
    money(AMOUNTS),
    st.decimals(min_value=0, max_value=100, allow_nan=False, allow_infinity=False, places=2),
)
def test_multiply_non_negative_factor_gives_non_negative(m: Money, factor: Decimal) -> None:
    result = m.multiply(factor)
    assert result.amount >= Decimal("0")


@given(
    money(POSITIVE_AMOUNTS),
    st.decimals(
        min_value=Decimal("-100"),
        max_value=Decimal("-0.01"),
        allow_nan=False,
        allow_infinity=False,
        places=2,
    ),
)
def test_multiply_negative_factor_raises(m: Money, factor: Decimal) -> None:
    with pytest.raises(ValidationError, match="negative"):
        m.multiply(factor)


@given(money(AMOUNTS))
def test_multiply_by_one_is_identity(m: Money) -> None:
    assert m.multiply(Decimal("1")) == m


@given(
    money(POSITIVE_AMOUNTS),
    st.decimals(
        min_value=Decimal("0.01"),
        max_value=Decimal("100"),
        allow_nan=False,
        allow_infinity=False,
        places=2,
    ),
)
def test_multiply_preserves_currency(m: Money, factor: Decimal) -> None:
    result = m.multiply(factor)
    assert result.currency == m.currency


# ---------------------------------------------------------------------------
# Construction invariants
# ---------------------------------------------------------------------------


@given(st.text(min_size=3, max_size=3, alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ"))
def test_valid_iso4217_accepted(code: str) -> None:
    """Three ASCII uppercase letters is a valid currency code."""
    m = Money(Decimal("1.00"), code)
    assert m.currency == code


@given(st.text(min_size=1, max_size=10).filter(lambda s: not (len(s) == 3 and s.isupper())))
def test_invalid_currency_rejected(code: str) -> None:
    with pytest.raises((ValidationError, Exception)):
        Money(Decimal("1.00"), code)


@given(
    st.decimals(
        min_value=Decimal("-10000"),
        max_value=Decimal("-0.01"),
        allow_nan=False,
        allow_infinity=False,
        places=2,
    )
)
def test_negative_amount_rejected(amount: Decimal) -> None:
    with pytest.raises(ValidationError, match="non-negative"):
        Money(amount, "USD")
