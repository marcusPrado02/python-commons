"""Application feature flags – FeatureFlagProvider port."""
from __future__ import annotations

import abc
from typing import Any

from mp_commons.application.feature_flags.feature_flag import FeatureFlag


class FeatureFlagProvider(abc.ABC):
    """Port: evaluate feature flags for a given context."""

    @abc.abstractmethod
    async def is_enabled(self, flag: FeatureFlag, context: dict[str, Any] | None = None) -> bool: ...

    @abc.abstractmethod
    async def get_variant(self, flag: FeatureFlag, context: dict[str, Any] | None = None) -> str | None: ...


__all__ = ["FeatureFlagProvider"]
