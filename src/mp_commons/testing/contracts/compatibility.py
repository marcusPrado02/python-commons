"""Schema compatibility asserter for contract tests."""

from __future__ import annotations

from typing import Any

__all__ = ["CompatibilityAsserter"]


class CompatibilityAsserter:
    """Assert schema compatibility between two versions of a contract."""

    def assert_backward_compatible(
        self,
        old_schema: dict[str, Any],
        new_schema: dict[str, Any],
    ) -> None:
        """Assert that *new_schema* can read documents produced by *old_schema*."""
        old_required = set(old_schema.get("required", []))
        new_props = set(new_schema.get("properties", {}).keys())
        missing = old_required - new_props
        if missing:
            raise AssertionError(
                f"Backward compatibility violated – fields removed: {missing}"
            )

    def assert_forward_compatible(
        self,
        old_schema: dict[str, Any],
        new_schema: dict[str, Any],
    ) -> None:
        """Assert that *old_schema* can read documents produced by *new_schema*."""
        new_required = set(new_schema.get("required", []))
        old_props = set(old_schema.get("properties", {}).keys())
        missing = new_required - old_props
        if missing:
            raise AssertionError(
                f"Forward compatibility violated – new required fields: {missing}"
            )
