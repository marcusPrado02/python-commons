"""Unit tests for kernel error hierarchy."""

from __future__ import annotations

import pytest

from mp_commons.kernel.errors import (
    ApplicationError,
    BaseError,
    ConflictError,
    DomainError,
    ExternalServiceError,
    ForbiddenError,
    InfrastructureError,
    InvariantViolationError,
    NotFoundError,
    RateLimitError,
    TimeoutError,
    UnauthorizedError,
    ValidationError,
)


class TestBaseError:
    def test_message_is_stored(self) -> None:
        err = BaseError("something went wrong")
        assert err.message == "something went wrong"

    def test_default_code(self) -> None:
        assert BaseError("m").code == "base_error"

    def test_custom_code(self) -> None:
        err = BaseError("m", code="custom")
        assert err.code == "custom"

    def test_to_dict(self) -> None:
        err = BaseError("m", code="my_code", detail={"key": "val"})
        d = err.to_dict()
        assert d == {"code": "my_code", "message": "m", "detail": {"key": "val"}}


class TestDomainErrors:
    def test_domain_error_is_base_error(self) -> None:
        assert issubclass(DomainError, BaseError)

    def test_not_found_formats_message(self) -> None:
        err = NotFoundError("Order", "123")
        assert "Order" in err.message
        assert "123" in err.message

    def test_not_found_without_id(self) -> None:
        err = NotFoundError("Product")
        assert "Product" in err.message
        assert err.identifier is None

    def test_validation_error_stores_errors(self) -> None:
        err = ValidationError("invalid", errors=[{"field": "email", "msg": "invalid"}])
        d = err.to_dict()
        assert "errors" in d
        assert d["errors"][0]["field"] == "email"

    def test_invariant_violation(self) -> None:
        with pytest.raises(InvariantViolationError, match="invariant"):
            raise InvariantViolationError("invariant broken")


class TestApplicationErrors:
    def test_forbidden_stores_permission(self) -> None:
        err = ForbiddenError(permission="orders:write")
        assert err.permission == "orders:write"

    def test_rate_limit_retry_after(self) -> None:
        err = RateLimitError(retry_after_seconds=30.0)
        assert err.retry_after_seconds == 30.0

    def test_unauthorized_inherits_application(self) -> None:
        assert issubclass(UnauthorizedError, ApplicationError)


class TestInfrastructureErrors:
    def test_external_service_error(self) -> None:
        err = ExternalServiceError("payments", status_code=503)
        assert err.service == "payments"
        assert err.status_code == 503

    def test_external_service_default_message(self) -> None:
        err = ExternalServiceError("stripe")
        assert "stripe" in err.message
