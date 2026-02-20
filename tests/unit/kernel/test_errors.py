"""Unit tests for kernel error hierarchy."""

from __future__ import annotations

import json

import pytest

from mp_commons.kernel.errors import (
    ApplicationError,
    BaseError,
    ConflictError,
    ConnectionError,
    DomainError,
    ExternalServiceError,
    ForbiddenError,
    InfrastructureError,
    InvariantViolationError,
    NotFoundError,
    RateLimitError,
    SerializationError,
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

    def test_to_dict_basic(self) -> None:
        err = BaseError("m", code="my_code", detail={"key": "val"})
        d = err.to_dict()
        assert d == {"code": "my_code", "message": "m", "detail": {"key": "val"}}

    def test_to_dict_includes_cause_repr(self) -> None:
        cause = ValueError("original")
        err = BaseError("wrapper", cause=cause)
        d = err.to_dict()
        assert "cause" in d
        assert "original" in d["cause"]

    def test_cause_sets_dunder_cause(self) -> None:
        cause = RuntimeError("root")
        err = BaseError("wrap", cause=cause)
        assert err.__cause__ is cause

    def test_str_is_valid_json(self) -> None:
        err = BaseError("oops", code="oops", detail={"x": 1})
        parsed = json.loads(str(err))
        assert parsed["code"] == "oops"
        assert parsed["message"] == "oops"

    def test_repr_contains_code_and_message(self) -> None:
        err = BaseError("hello", code="hi")
        r = repr(err)
        assert "hi" in r
        assert "hello" in r

    def test_context_propagation(self) -> None:
        ctx = {"order_id": "ord-1", "tenant": "acme"}
        err = BaseError("ctx test", detail=ctx)
        assert err.detail["order_id"] == "ord-1"
        assert err.to_dict()["detail"]["tenant"] == "acme"

    def test_is_exception(self) -> None:
        with pytest.raises(BaseError):
            raise BaseError("boom")


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

    def test_validation_error_empty_errors_default(self) -> None:
        err = ValidationError("bad input")
        assert err.errors == []

    def test_invariant_violation(self) -> None:
        with pytest.raises(InvariantViolationError, match="invariant"):
            raise InvariantViolationError("invariant broken")

    def test_conflict_error(self) -> None:
        err = ConflictError("duplicate key")
        assert err.code == "conflict"
        assert issubclass(ConflictError, DomainError)


class TestApplicationErrors:
    def test_forbidden_stores_permission(self) -> None:
        err = ForbiddenError(permission="orders:write")
        assert err.permission == "orders:write"

    def test_rate_limit_retry_after(self) -> None:
        err = RateLimitError(retry_after_seconds=30.0)
        assert err.retry_after_seconds == 30.0

    def test_unauthorized_inherits_application(self) -> None:
        assert issubclass(UnauthorizedError, ApplicationError)

    def test_timeout_inherits_application(self) -> None:
        assert issubclass(TimeoutError, ApplicationError)

    def test_all_inherit_base_error(self) -> None:
        for cls in (UnauthorizedError, ForbiddenError, RateLimitError, TimeoutError):
            assert issubclass(cls, BaseError)


class TestInfrastructureErrors:
    def test_external_service_error(self) -> None:
        err = ExternalServiceError("payments", status_code=503)
        assert err.service == "payments"
        assert err.status_code == 503

    def test_external_service_default_message(self) -> None:
        err = ExternalServiceError("stripe")
        assert "stripe" in err.message

    def test_connection_error_message(self) -> None:
        err = ConnectionError("postgres")
        assert "postgres" in err.message
        assert err.resource == "postgres"
        assert err.code == "connection_error"

    def test_connection_error_custom_message(self) -> None:
        err = ConnectionError("redis", "timed out after 5 s")
        assert err.message == "timed out after 5 s"

    def test_serialization_error(self) -> None:
        err = SerializationError("bad JSON", payload_type="OrderCreated")
        assert err.payload_type == "OrderCreated"
        assert err.code == "serialization_error"

    def test_infrastructure_timeout(self) -> None:
        from mp_commons.kernel.errors import InfrastructureTimeoutError

        err = InfrastructureTimeoutError("query too slow")
        assert issubclass(InfrastructureTimeoutError, InfrastructureError)
        assert err.code == "infrastructure_timeout"

    def test_cause_chaining_across_hierarchy(self) -> None:
        root = IOError("disk full")
        infra = InfrastructureError("storage failed", cause=root)
        domain = DomainError("order save failed", cause=infra)
        assert domain.__cause__ is infra
        assert infra.__cause__ is root
        assert "cause" in domain.to_dict()
        assert "cause" in infra.to_dict()
