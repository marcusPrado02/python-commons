"""Unit tests for testing contracts (§40)."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from mp_commons.testing.contracts import (
    AsyncAPIContractTest,
    CompatibilityAsserter,
    OpenAPIContractTest,
)


# ---------------------------------------------------------------------------
# Helpers — subclasses that bypass HTTP calls
# ---------------------------------------------------------------------------


class _StubbedOpenAPI(OpenAPIContractTest):
    """Subclass that returns a pre-set spec without making HTTP requests."""

    def __init__(self, spec: dict[str, Any]) -> None:
        self._spec = spec

    async def load_spec(self) -> dict[str, Any]:  # type: ignore[override]
        return self._spec


class _StubbedAsyncAPI(AsyncAPIContractTest):
    """Subclass that returns a pre-set spec without making HTTP requests."""

    def __init__(self, spec: dict[str, Any]) -> None:
        self._spec = spec

    async def load_spec(self) -> dict[str, Any]:  # type: ignore[override]
        return self._spec


# ---------------------------------------------------------------------------
# §40.1  OpenAPIContractTest
# ---------------------------------------------------------------------------


class TestOpenAPIContractTest:
    def test_valid_spec_passes(self) -> None:
        spec = {"openapi": "3.0.0", "info": {}, "paths": {"/health": {}}}
        ct = _StubbedOpenAPI(spec)
        asyncio.run(ct.assert_valid_schema())  # must not raise

    def test_missing_openapi_key_fails(self) -> None:
        spec = {"paths": {"/health": {}}}
        ct = _StubbedOpenAPI(spec)
        with pytest.raises(AssertionError, match="Not a valid OpenAPI"):
            asyncio.run(ct.assert_valid_schema())

    def test_missing_paths_key_fails(self) -> None:
        spec = {"openapi": "3.1.0", "info": {}}
        ct = _StubbedOpenAPI(spec)
        with pytest.raises(AssertionError, match="no paths"):
            asyncio.run(ct.assert_valid_schema())

    def test_default_openapi_url_is_empty_string(self) -> None:
        ct = OpenAPIContractTest()
        assert ct.openapi_url == ""

    def test_subclass_can_override_openapi_url(self) -> None:
        class MyTest(OpenAPIContractTest):
            openapi_url = "http://localhost:8000/openapi.json"

        assert MyTest().openapi_url == "http://localhost:8000/openapi.json"

    def test_load_spec_returns_dict(self) -> None:
        spec = {"openapi": "3.0.0", "paths": {}}
        ct = _StubbedOpenAPI(spec)
        result = asyncio.run(ct.load_spec())
        assert result == spec

    def test_importable_from_module(self) -> None:
        from mp_commons.testing.contracts.openapi import (
            OpenAPIContractTest as _OAct,
        )
        assert _OAct is OpenAPIContractTest


# ---------------------------------------------------------------------------
# §40.2  AsyncAPIContractTest
# ---------------------------------------------------------------------------


class TestAsyncAPIContractTest:
    def test_valid_spec_passes(self) -> None:
        spec = {"asyncapi": "2.6.0", "info": {}, "channels": {"user/signedup": {}}}
        ct = _StubbedAsyncAPI(spec)
        asyncio.run(ct.assert_valid_schema())  # must not raise

    def test_missing_asyncapi_key_fails(self) -> None:
        spec = {"channels": {"user/signedup": {}}}
        ct = _StubbedAsyncAPI(spec)
        with pytest.raises(AssertionError, match="Not a valid AsyncAPI"):
            asyncio.run(ct.assert_valid_schema())

    def test_missing_channels_key_fails(self) -> None:
        spec = {"asyncapi": "2.6.0", "info": {}}
        ct = _StubbedAsyncAPI(spec)
        with pytest.raises(AssertionError, match="no channels"):
            asyncio.run(ct.assert_valid_schema())

    def test_default_asyncapi_url_is_empty_string(self) -> None:
        ct = AsyncAPIContractTest()
        assert ct.asyncapi_url == ""

    def test_load_spec_returns_dict(self) -> None:
        spec = {"asyncapi": "2.6.0", "channels": {}}
        ct = _StubbedAsyncAPI(spec)
        result = asyncio.run(ct.load_spec())
        assert result == spec

    def test_importable_from_module(self) -> None:
        from mp_commons.testing.contracts.asyncapi import (
            AsyncAPIContractTest as _AAct,
        )
        assert _AAct is AsyncAPIContractTest


# ---------------------------------------------------------------------------
# §40.3  CompatibilityAsserter
# ---------------------------------------------------------------------------


class TestCompatibilityAsserter:
    # --- backward compatibility ---

    def test_backward_identical_schemas_pass(self) -> None:
        s = {"properties": {"id": {}, "name": {}}, "required": ["id", "name"]}
        CompatibilityAsserter().assert_backward_compatible(s, s)

    def test_backward_new_optional_field_ok(self) -> None:
        """New schema adds an optional field — backward-compatible."""
        old = {"properties": {"id": {}}, "required": ["id"]}
        new = {"properties": {"id": {}, "extra": {}}, "required": ["id"]}
        CompatibilityAsserter().assert_backward_compatible(old, new)

    def test_backward_removed_required_field_fails(self) -> None:
        """New schema drops a field that was required in old — breaks readers."""
        old = {"properties": {"id": {}, "name": {}}, "required": ["id", "name"]}
        new = {"properties": {"id": {}}, "required": ["id"]}
        with pytest.raises(AssertionError, match="Backward compatibility violated"):
            CompatibilityAsserter().assert_backward_compatible(old, new)

    def test_backward_required_turned_optional_ok(self) -> None:
        """Field stays in properties but removed from required list — still readable."""
        old = {"properties": {"id": {}, "name": {}}, "required": ["id", "name"]}
        new = {"properties": {"id": {}, "name": {}}, "required": ["id"]}
        CompatibilityAsserter().assert_backward_compatible(old, new)

    def test_backward_empty_schemas_pass(self) -> None:
        CompatibilityAsserter().assert_backward_compatible({}, {})

    def test_backward_old_has_no_required_always_passes(self) -> None:
        old = {"properties": {"id": {}}}
        new = {"properties": {"id": {}}}
        CompatibilityAsserter().assert_backward_compatible(old, new)

    def test_backward_error_lists_missing_fields(self) -> None:
        old = {"properties": {"id": {}, "a": {}, "b": {}}, "required": ["id", "a", "b"]}
        new = {"properties": {"id": {}}, "required": ["id"]}
        with pytest.raises(AssertionError) as exc_info:
            CompatibilityAsserter().assert_backward_compatible(old, new)
        msg = str(exc_info.value)
        assert "a" in msg or "b" in msg

    # --- forward compatibility ---

    def test_forward_identical_schemas_pass(self) -> None:
        s = {"properties": {"id": {}, "name": {}}, "required": ["id", "name"]}
        CompatibilityAsserter().assert_forward_compatible(s, s)

    def test_forward_new_optional_field_ok(self) -> None:
        """New schema adds optional field — old readers can ignore unknown fields."""
        old = {"properties": {"id": {}}, "required": ["id"]}
        new = {"properties": {"id": {}, "extra": {}}, "required": ["id"]}
        CompatibilityAsserter().assert_forward_compatible(old, new)

    def test_forward_new_required_field_fails(self) -> None:
        """New schema adds a REQUIRED field old schema doesn't have — breaks old readers."""
        old = {"properties": {"id": {}}, "required": ["id"]}
        new = {"properties": {"id": {}, "name": {}}, "required": ["id", "name"]}
        with pytest.raises(AssertionError, match="Forward compatibility violated"):
            CompatibilityAsserter().assert_forward_compatible(old, new)

    def test_forward_empty_schemas_pass(self) -> None:
        CompatibilityAsserter().assert_forward_compatible({}, {})

    def test_forward_error_lists_new_required_fields(self) -> None:
        old = {"properties": {"id": {}}, "required": ["id"]}
        new = {"properties": {"id": {}, "x": {}, "y": {}}, "required": ["id", "x", "y"]}
        with pytest.raises(AssertionError) as exc_info:
            CompatibilityAsserter().assert_forward_compatible(old, new)
        msg = str(exc_info.value)
        assert "x" in msg or "y" in msg


# ---------------------------------------------------------------------------
# §40.4  __init__ exports
# ---------------------------------------------------------------------------


class TestContractsInit:
    def test_all_classes_importable(self) -> None:
        from mp_commons.testing.contracts import (
            AsyncAPIContractTest as A,
            CompatibilityAsserter as C,
            OpenAPIContractTest as O,
        )
        assert A is AsyncAPIContractTest
        assert C is CompatibilityAsserter
        assert O is OpenAPIContractTest

    def test_openapi_is_subclassable(self) -> None:
        class MyAPI(OpenAPIContractTest):
            openapi_url = "http://example.com/openapi.json"
        assert issubclass(MyAPI, OpenAPIContractTest)

    def test_asyncapi_is_subclassable(self) -> None:
        class MyAPI(AsyncAPIContractTest):
            asyncapi_url = "http://example.com/asyncapi.json"
        assert issubclass(MyAPI, AsyncAPIContractTest)

    def test_compatibility_asserter_is_instantiable(self) -> None:
        assert isinstance(CompatibilityAsserter(), CompatibilityAsserter)
