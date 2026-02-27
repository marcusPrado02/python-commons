"""§90 Config — Remote Feature Flags (OpenFeature compatible)."""
from __future__ import annotations

from mp_commons.config.flags.provider import (
    EvaluationContext,
    FlatFileProvider,
    FlagProvider,
    FeatureFlagClient,
)

__all__ = [
    "EvaluationContext",
    "FeatureFlagClient",
    "FlatFileProvider",
    "FlagProvider",
]
