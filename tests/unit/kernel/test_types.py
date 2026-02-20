"""Unit tests for kernel types."""

from __future__ import annotations

import pytest
from decimal import Decimal

from mp_commons.kernel.errors import ValidationError
from mp_commons.kernel.types import (
    Email,
    Err,
    Money,
    Nothing,
    Ok,
    PhoneNumber,
    Slug,
    Some,
    TenantId,
    EntityId,
)


class TestEntityId:
    def test_empty_raises(self) -> None:
        with pytest.raises(ValidationError):
            EntityId("")

    def test_str_representation(self) -> None:
        assert str(EntityId("abc-123")) == "abc-123"

    def test_equality(self) -> None:
        assert EntityId("a") == EntityId("a")
        assert EntityId("a") != EntityId("b")


class TestEmail:
    def test_valid_email(self) -> None:
        e = Email("User@Example.COM")
        assert e.value == "user@example.com"  # normalised

    def test_invalid_email_raises(self) -> None:
        with pytest.raises(ValidationError):
            Email("not-an-email")

    def test_str_output(self) -> None:
        assert str(Email("a@b.com")) == "a@b.com"


class TestMoney:
    def test_valid_money(self) -> None:
        m = Money.of("99.99", "BRL")
        assert m.amount == Decimal("99.99")
        assert m.currency == "BRL"

    def test_invalid_currency(self) -> None:
        with pytest.raises(ValidationError):
            Money.of(1, "usd")  # lowercase

    def test_negative_raises(self) -> None:
        with pytest.raises(ValidationError):
            Money.of(-1, "BRL")

    def test_addition_same_currency(self) -> None:
        a = Money.of("10.00", "USD")
        b = Money.of("5.00", "USD")
        assert (a + b).amount == Decimal("15.00")

    def test_addition_different_currency_raises(self) -> None:
        with pytest.raises(ValidationError):
            Money.of("10.00", "USD") + Money.of("5.00", "BRL")

    def test_subtraction_underflow_raises(self) -> None:
        with pytest.raises(ValidationError):
            Money.of("5.00", "USD") - Money.of("10.00", "USD")


class TestPhoneNumber:
    def test_valid_e164(self) -> None:
        p = PhoneNumber("+5511999999999")
        assert str(p) == "+5511999999999"

    def test_invalid_raises(self) -> None:
        with pytest.raises(ValidationError):
            PhoneNumber("11999999999")


class TestSlug:
    def test_valid_slug(self) -> None:
        s = Slug("my-cool-slug")
        assert str(s) == "my-cool-slug"

    def test_invalid_slug_raises(self) -> None:
        with pytest.raises(ValidationError):
            Slug("UPPERCASE")


class TestResultMonad:
    def test_ok_unwrap(self) -> None:
        ok = Ok(42)
        assert ok.unwrap() == 42

    def test_ok_is_ok(self) -> None:
        assert Ok(1).is_ok()
        assert not Ok(1).is_err()

    def test_err_unwrap_raises(self) -> None:
        err = Err(ValueError("boom"))
        with pytest.raises(ValueError, match="boom"):
            err.unwrap()

    def test_err_unwrap_or(self) -> None:
        assert Err(ValueError()).unwrap_or(99) == 99

    def test_ok_map(self) -> None:
        ok = Ok(2)
        assert ok.map(lambda x: x * 3).unwrap() == 6


class TestOptionMonad:
    def test_some_is_some(self) -> None:
        s = Some(10)
        assert s.is_some()
        assert not s.is_none()

    def test_nothing_is_none(self) -> None:
        n: Nothing[int] = Nothing()
        assert n.is_none()
        assert not n.is_some()

    def test_nothing_unwrap_raises(self) -> None:
        with pytest.raises(ValueError):
            Nothing().unwrap()

    def test_some_iter(self) -> None:
        assert list(Some(5)) == [5]

    def test_nothing_iter(self) -> None:
        assert list(Nothing()) == []
