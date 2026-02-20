"""Unit tests for kernel types."""

from __future__ import annotations

from decimal import Decimal

import pytest

from mp_commons.kernel.errors import ValidationError
from mp_commons.kernel.types import (
    CorrelationId,
    Email,
    EntityId,
    Err,
    Money,
    Nothing,
    Ok,
    PhoneNumber,
    Slug,
    Some,
    TenantId,
    UID,
    ULID,
    UUIDv7,
)


# ---------------------------------------------------------------------------
# EntityId
# ---------------------------------------------------------------------------


class TestEntityId:
    def test_empty_raises(self) -> None:
        with pytest.raises(ValidationError):
            EntityId("")

    def test_str_representation(self) -> None:
        assert str(EntityId("abc-123")) == "abc-123"

    def test_equality(self) -> None:
        assert EntityId("a") == EntityId("a")
        assert EntityId("a") != EntityId("b")

    def test_generate_returns_non_empty(self) -> None:
        eid = EntityId.generate()
        assert isinstance(eid, EntityId)
        assert len(eid.value) > 0

    def test_generate_produces_unique_values(self) -> None:
        ids = {EntityId.generate().value for _ in range(20)}
        assert len(ids) == 20

    def test_from_str_round_trips(self) -> None:
        raw = "my-custom-id-42"
        eid = EntityId.from_str(raw)
        assert eid.value == raw

    def test_from_str_empty_raises(self) -> None:
        with pytest.raises(ValidationError):
            EntityId.from_str("")


class TestCorrelationId:
    def test_generate_returns_correlation_id(self) -> None:
        cid = CorrelationId.generate()
        assert isinstance(cid, CorrelationId)
        assert len(cid.value) > 0

    def test_direct_construction(self) -> None:
        cid = CorrelationId("trace-001")
        assert str(cid) == "trace-001"


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------


class TestEmail:
    def test_valid_email_normalised_to_lowercase(self) -> None:
        e = Email("User@Example.COM")
        assert e.value == "user@example.com"

    def test_invalid_email_raises(self) -> None:
        with pytest.raises(ValidationError):
            Email("not-an-email")

    def test_str_output(self) -> None:
        assert str(Email("a@b.com")) == "a@b.com"

    def test_domain_simple(self) -> None:
        assert Email("alice@example.com").domain == "example.com"

    def test_domain_subdomain(self) -> None:
        assert Email("bob@mail.corp.io").domain == "mail.corp.io"

    def test_domain_at_in_local_part_not_affected(self) -> None:
        # Only the first @ separates local from domain
        e = Email("user@sub.domain.org")
        assert e.domain == "sub.domain.org"


# ---------------------------------------------------------------------------
# Money
# ---------------------------------------------------------------------------


class TestMoney:
    def test_valid_money(self) -> None:
        m = Money.of("99.99", "BRL")
        assert m.amount == Decimal("99.99")
        assert m.currency == "BRL"

    def test_invalid_currency_direct_constructor(self) -> None:
        # The constructor validates but does NOT normalise; lowercase must fail.
        with pytest.raises(ValidationError):
            Money(Decimal("1"), "usd")

    def test_factory_normalises_currency_to_upper(self) -> None:
        # Money.of() applies .upper() so lowercase is accepted and normalised.
        m = Money.of(1, "usd")
        assert m.currency == "USD"

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

    def test_multiply_integer(self) -> None:
        m = Money.of("10.00", "USD")
        assert m.multiply(3).amount == Decimal("30.00")
        assert m.multiply(3).currency == "USD"

    def test_multiply_float(self) -> None:
        m = Money.of("10.00", "USD")
        result = m.multiply(1.5)
        assert result.amount == Decimal("15.0")

    def test_multiply_zero(self) -> None:
        m = Money.of("50.00", "EUR")
        assert m.multiply(0).amount == Decimal("0")

    def test_multiply_negative_raises(self) -> None:
        m = Money.of("10.00", "USD")
        with pytest.raises(ValidationError):
            m.multiply(-1)

    def test_multiply_decimal_factor(self) -> None:
        m = Money.of("100.00", "BRL")
        assert m.multiply(Decimal("0.1")).amount == Decimal("10.000")


# ---------------------------------------------------------------------------
# PhoneNumber
# ---------------------------------------------------------------------------


class TestPhoneNumber:
    def test_valid_e164(self) -> None:
        p = PhoneNumber("+5511999999999")
        assert str(p) == "+5511999999999"

    def test_invalid_raises(self) -> None:
        with pytest.raises(ValidationError):
            PhoneNumber("11999999999")

    # country code heuristics
    def test_country_code_us(self) -> None:
        p = PhoneNumber("+12125551234")
        assert p.country_code == "1"
        assert p.national_number == "2125551234"

    def test_country_code_brazil(self) -> None:
        # Brazil is +55 (2-digit CC)
        p = PhoneNumber("+5511999990000")
        assert p.country_code == "55"
        assert p.national_number == "11999990000"

    def test_national_number_length(self) -> None:
        p = PhoneNumber("+447911123456")
        cc = p.country_code
        assert p.national_number == p.value[1 + len(cc):]


# ---------------------------------------------------------------------------
# Slug
# ---------------------------------------------------------------------------


class TestSlug:
    def test_valid_slug(self) -> None:
        s = Slug("my-cool-slug")
        assert str(s) == "my-cool-slug"

    def test_invalid_slug_raises(self) -> None:
        with pytest.raises(ValidationError):
            Slug("UPPERCASE")

    def test_from_text_basic(self) -> None:
        assert Slug.from_text("Hello World").value == "hello-world"

    def test_from_text_strips_special_chars(self) -> None:
        assert Slug.from_text("Python 3.12!").value == "python-312"

    def test_from_text_underscores_become_hyphens(self) -> None:
        assert Slug.from_text("some_snake_case").value == "some-snake-case"

    def test_from_text_collapses_multiple_hyphens(self) -> None:
        s = Slug.from_text("foo---bar")
        assert s.value == "foo-bar"

    def test_from_text_strips_leading_trailing_hyphens(self) -> None:
        s = Slug.from_text("  -hello- ")
        assert not s.value.startswith("-")
        assert not s.value.endswith("-")

    def test_from_text_already_valid_slug(self) -> None:
        assert Slug.from_text("already-fine").value == "already-fine"


# ---------------------------------------------------------------------------
# Result monad
# ---------------------------------------------------------------------------


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

    def test_ok_flat_map_returns_inner_ok(self) -> None:
        ok: Ok[int] = Ok(5)
        result = ok.flat_map(lambda x: Ok(x * 2))
        assert result.unwrap() == 10

    def test_ok_flat_map_can_return_err(self) -> None:
        ok: Ok[int] = Ok(0)
        result = ok.flat_map(lambda x: Err(ValueError("zero")) if x == 0 else Ok(x))
        assert result.is_err()

    def test_err_flat_map_is_identity(self) -> None:
        err: Err[ValueError] = Err(ValueError("original"))
        result = err.flat_map(lambda x: Ok(x))
        assert result.is_err()

    def test_ok_err_repr(self) -> None:
        assert repr(Ok(1)) == "Ok(1)"
        assert "Err" in repr(Err(ValueError("x")))


# ---------------------------------------------------------------------------
# Option monad
# ---------------------------------------------------------------------------


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

    def test_some_flat_map_returns_inner(self) -> None:
        result = Some(3).flat_map(lambda x: Some(x * 2))
        assert result.unwrap() == 6

    def test_some_flat_map_can_return_nothing(self) -> None:
        result = Some(0).flat_map(lambda x: Nothing() if x == 0 else Some(x))
        assert result.is_none()

    def test_nothing_flat_map_is_identity(self) -> None:
        n: Nothing[int] = Nothing()
        result = n.flat_map(lambda x: Some(x))
        assert result.is_none()

    def test_some_filter_passes(self) -> None:
        result = Some(4).filter(lambda x: x > 0)
        assert result.is_some()
        assert result.unwrap() == 4

    def test_some_filter_fails(self) -> None:
        result = Some(-1).filter(lambda x: x > 0)
        assert result.is_none()

    def test_nothing_filter_is_identity(self) -> None:
        n: Nothing[int] = Nothing()
        result = n.filter(lambda x: True)
        assert result.is_none()


# ---------------------------------------------------------------------------
# UID
# ---------------------------------------------------------------------------


class TestUID:
    def test_generate_returns_12_chars(self) -> None:
        uid = UID.generate()
        assert len(uid.value) == 12

    def test_generate_url_safe(self) -> None:
        # URL-safe base64 chars: A-Z a-z 0-9 - _
        import re
        uid = UID.generate()
        assert re.fullmatch(r"[A-Za-z0-9\-_]{12}", uid.value)

    def test_generate_unique(self) -> None:
        uids = {UID.generate().value for _ in range(50)}
        assert len(uids) == 50

    def test_str(self) -> None:
        uid = UID.generate()
        assert str(uid) == uid.value

    def test_invalid_length_raises(self) -> None:
        with pytest.raises(ValidationError):
            UID("short")

    def test_equality(self) -> None:
        uid = UID.generate()
        assert uid == UID(uid.value)


# ---------------------------------------------------------------------------
# ULID (smoke tests — optional dep)
# ---------------------------------------------------------------------------


class TestULIDSmoke:
    def test_valid_ulid_string(self) -> None:
        # Known valid ULID (26 Crockford base32 chars)
        ulid = ULID("01ARZ3NDEKTSV4RRFFQ69G5FAV")
        assert str(ulid) == "01ARZ3NDEKTSV4RRFFQ69G5FAV"

    def test_invalid_ulid_raises(self) -> None:
        with pytest.raises(ValidationError):
            ULID("not-a-ulid")


# ---------------------------------------------------------------------------
# Public re-export surface
# ---------------------------------------------------------------------------


class TestPublicReExports:
    """Ensure everything declared in __all__ is importable."""

    def test_uid_in_public_api(self) -> None:
        from mp_commons.kernel import types as t
        assert hasattr(t, "UID")

    def test_all_symbols_importable(self) -> None:
        import importlib
        mod = importlib.import_module("mp_commons.kernel.types")
        for name in mod.__all__:
            assert hasattr(mod, name), f"{name!r} listed in __all__ but not found"
