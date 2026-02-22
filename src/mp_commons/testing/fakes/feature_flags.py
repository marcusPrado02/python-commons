"""Testing fakes – FakeFeatureFlagProvider (§36.9)."""
from __future__ import annotations

from typing import Any

from mp_commons.application.feature_flags.feature_flag import FeatureFlag
from mp_commons.application.feature_flags.provider import FeatureFlagProvider


class FakeFeatureFlagProvider(FeatureFlagProvider):
    """In-memory :class:`FeatureFlagProvider` backed by a plain ``dict``.

    Use :meth:`enable` / :meth:`disable` to configure flags before running the
    code under test; use :meth:`set_variant` to control variant values.

    Usage::

        flags = FakeFeatureFlagProvider()
        flags.enable("new_checkout_flow")

        result = await flags.is_enabled(FeatureFlag("new_checkout_flow"))
        assert result is True
    """

    def __init__(self, *, default: bool = False) -> None:
        self._enabled: dict[str, bool] = {}
        self._variants: dict[str, str | None] = {}
        self._default = default

    # ------------------------------------------------------------------
    # FeatureFlagProvider protocol
    # ------------------------------------------------------------------

    async def is_enabled(
        self, flag: FeatureFlag, context: dict[str, Any] | None = None
    ) -> bool:
        if flag.key in self._enabled:
            return self._enabled[flag.key]
        return flag.default_value if self._default is False else self._default

    async def get_variant(
        self, flag: FeatureFlag, context: dict[str, Any] | None = None
    ) -> str | None:
        return self._variants.get(flag.key)

    # ------------------------------------------------------------------
    # Test-setup helpers
    # ------------------------------------------------------------------

    def enable(self, flag: str | FeatureFlag) -> "FakeFeatureFlagProvider":
        """Enable *flag* (by key string or :class:`FeatureFlag` instance)."""
        key = flag.key if isinstance(flag, FeatureFlag) else flag
        self._enabled[key] = True
        return self

    def disable(self, flag: str | FeatureFlag) -> "FakeFeatureFlagProvider":
        """Disable *flag*."""
        key = flag.key if isinstance(flag, FeatureFlag) else flag
        self._enabled[key] = False
        return self

    def set_variant(
        self, flag: str | FeatureFlag, variant: str | None
    ) -> "FakeFeatureFlagProvider":
        """Set the variant returned by :meth:`get_variant`."""
        key = flag.key if isinstance(flag, FeatureFlag) else flag
        self._variants[key] = variant
        return self

    def reset(self) -> None:
        """Clear all configured flags (useful between test cases)."""
        self._enabled.clear()
        self._variants.clear()


__all__ = ["FakeFeatureFlagProvider"]
