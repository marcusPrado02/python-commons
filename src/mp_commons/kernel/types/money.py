"""Money value object with ISO-4217 currency validation."""

from __future__ import annotations

import dataclasses
import re
from decimal import Decimal
from typing import Any, Final

from mp_commons.kernel.errors.domain import ValidationError

_ISO4217: Final = re.compile(r"^[A-Z]{3}$")


@dataclasses.dataclass(frozen=True, slots=True)
class Money:
    """Immutable monetary amount with explicit currency."""

    amount: Decimal
    currency: str  # ISO 4217

    def __post_init__(self) -> None:
        if not _ISO4217.match(self.currency):
            raise ValidationError(f"Invalid ISO 4217 currency code: {self.currency!r}")
        if self.amount < 0:
            raise ValidationError("Money amount must be non-negative")

    def __add__(self, other: "Money") -> "Money":
        self._assert_same_currency(other)
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: "Money") -> "Money":
        self._assert_same_currency(other)
        result = self.amount - other.amount
        if result < 0:
            raise ValidationError("Subtraction would produce negative Money")
        return Money(result, self.currency)

    def _assert_same_currency(self, other: "Money") -> None:
        if self.currency != other.currency:
            raise ValidationError(
                f"Currency mismatch: {self.currency} vs {other.currency}"
            )

    @classmethod
    def of(cls, amount: "str | int | float | Decimal", currency: str) -> "Money":
        return cls(Decimal(str(amount)), currency.upper())

    def multiply(self, factor: "int | float | Decimal") -> "Money":
        """Return a new ``Money`` scaled by *factor* (must keep amount non-negative)."""
        result = self.amount * Decimal(str(factor))
        if result < 0:
            raise ValidationError("multiply() would produce negative Money")
        return Money(result, self.currency)

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: Any,
        handler: Any,
    ) -> Any:
        try:
            from pydantic_core import core_schema

            def _validate(v: Any) -> "Money":
                if isinstance(v, cls):
                    return v
                if isinstance(v, dict):
                    return cls.of(v["amount"], v["currency"])
                raise ValueError(f"Cannot convert {v!r} to Money")

            return core_schema.no_info_plain_validator_function(
                _validate,
                serialization=core_schema.plain_serializer_function_ser_schema(
                    lambda m: {"amount": str(m.amount), "currency": m.currency},
                ),
            )
        except ImportError:
            raise


__all__ = ["Money"]
