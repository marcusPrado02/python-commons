"""Application feature flags – InMemoryFeatureFlagProvider."""

from __future__ import annotations

from typing import Any

from mp_commons.application.feature_flags.feature_flag import FeatureFlag
from mp_commons.application.feature_flags.provider import FeatureFlagProvider


class InMemoryFeatureFlagProvider(FeatureFlagProvider):
    """Simple in-memory provider backed by a ``{key: bool}`` dict."""

    def __init__(self, flags: dict[str, bool] | None = None) -> None:
        self._flags: dict[str, bool] = dict(flags or {})

    def set(self, flag: FeatureFlag | str, enabled: bool) -> None:
        """Enable or disable a flag by key or :class:`FeatureFlag` instance."""
        key = flag.key if isinstance(flag, FeatureFlag) else flag
        self._flags[key] = enabled

    async def is_enabled(
        self, flag: FeatureFlag, context: dict[str, Any] | None = None
    ) -> bool:
        return self._flags.get(flag.key, flag.default_value)

    async def get_variant(
        self, flag: FeatureFlag, context: dict[str, Any] | None = None
    ) -> str | None:
        enabled = self._flags.get(flag.key, flag.default_value)
        return "on" if enabled else "off"


__all__ = ["InMemoryFeatureFlagProvider"]
