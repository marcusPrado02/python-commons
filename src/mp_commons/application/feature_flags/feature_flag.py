"""Application feature flags – FeatureFlag value object."""
from __future__ import annotations

import dataclasses


@dataclasses.dataclass(frozen=True)
class FeatureFlag:
    """Describes a feature flag with metadata."""
    key: str
    description: str = ""
    default_value: bool = False
    tags: frozenset[str] = frozenset()


__all__ = ["FeatureFlag"]
