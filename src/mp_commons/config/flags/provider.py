"""Feature flag providers — OpenFeature-compatible interface."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

__all__ = [
    "EvaluationContext",
    "FeatureFlagClient",
    "FlatFileProvider",
    "FlagProvider",
]


@dataclass
class EvaluationContext:
    """Carries user / request context for flag evaluation."""

    targeting_key: str = ""
    attributes: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class FlagProvider(Protocol):
    """OpenFeature-style provider interface."""

    async def get_boolean(
        self, flag_key: str, default: bool, context: EvaluationContext | None = None
    ) -> bool:
        ...

    async def get_string(
        self, flag_key: str, default: str, context: EvaluationContext | None = None
    ) -> str:
        ...

    async def get_number(
        self, flag_key: str, default: float, context: EvaluationContext | None = None
    ) -> float:
        ...

    async def get_object(
        self, flag_key: str, default: Any, context: EvaluationContext | None = None
    ) -> Any:
        ...


class FeatureFlagClient:
    """Thin client delegate that wraps a ``FlagProvider``."""

    def __init__(self, provider: FlagProvider) -> None:
        self._provider = provider

    async def is_enabled(
        self,
        flag_key: str,
        default: bool = False,
        context: EvaluationContext | None = None,
    ) -> bool:
        try:
            return await self._provider.get_boolean(flag_key, default, context)
        except Exception:  # noqa: BLE001
            return default

    async def get_string(
        self, flag_key: str, default: str = "", context: EvaluationContext | None = None
    ) -> str:
        try:
            return await self._provider.get_string(flag_key, default, context)
        except Exception:  # noqa: BLE001
            return default

    async def get_number(
        self, flag_key: str, default: float = 0.0, context: EvaluationContext | None = None
    ) -> float:
        try:
            return await self._provider.get_number(flag_key, default, context)
        except Exception:  # noqa: BLE001
            return default

    async def get_object(
        self, flag_key: str, default: Any = None, context: EvaluationContext | None = None
    ) -> Any:
        try:
            return await self._provider.get_object(flag_key, default, context)
        except Exception:  # noqa: BLE001
            return default


# ---------------------------------------------------------------------------
# FlatFileProvider
# ---------------------------------------------------------------------------

def _percentage_bucket(targeting_key: str, flag_key: str) -> float:
    """Deterministic 0-100 bucket for a given user+flag combination."""
    digest = hashlib.sha256(f"{flag_key}:{targeting_key}".encode()).hexdigest()
    return (int(digest[:8], 16) % 100_000) / 1_000  # 0.000–99.999


class FlatFileProvider:
    """Read feature flags from a YAML file.

    YAML schema example::

        my_feature:
          enabled: true
          rollout_percentage: 50
          targeting:
            - key: "user-123"
              value: true

        my_string_flag:
          value: "blue"
    """

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._flags: dict[str, Any] = {}
        self._loaded = False

    def _load(self) -> dict[str, Any]:
        import yaml
        raw = self._path.read_text()
        return yaml.safe_load(raw) or {}

    def reload(self) -> None:
        self._flags = self._load()
        self._loaded = True

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self.reload()

    def _evaluate_boolean(
        self, flag_def: dict[str, Any], context: EvaluationContext | None
    ) -> bool:
        # Targeting rules first
        if context and (targeting := flag_def.get("targeting")):
            for rule in targeting:
                if rule.get("key") == context.targeting_key:
                    return bool(rule.get("value", False))
            for rule in targeting:
                for attr_key, attr_val in context.attributes.items():
                    if rule.get("key") == attr_key and rule.get("match") == attr_val:
                        return bool(rule.get("value", False))

        # Rollout percentage
        if (pct := flag_def.get("rollout_percentage")) is not None:
            targeting_key = (context.targeting_key if context else "") or ""
            flag_key = flag_def.get("_key", "")
            bucket = _percentage_bucket(targeting_key, flag_key)
            return bucket < float(pct)

        return bool(flag_def.get("enabled", False))

    async def get_boolean(
        self, flag_key: str, default: bool, context: EvaluationContext | None = None
    ) -> bool:
        self._ensure_loaded()
        flag_def = self._flags.get(flag_key)
        if flag_def is None:
            return default
        if not isinstance(flag_def, dict):
            return bool(flag_def)
        flag_def = dict(flag_def, _key=flag_key)
        return self._evaluate_boolean(flag_def, context)

    async def get_string(
        self, flag_key: str, default: str, context: EvaluationContext | None = None
    ) -> str:
        self._ensure_loaded()
        flag_def = self._flags.get(flag_key)
        if flag_def is None:
            return default
        if isinstance(flag_def, dict):
            return str(flag_def.get("value", default))
        return str(flag_def)

    async def get_number(
        self, flag_key: str, default: float, context: EvaluationContext | None = None
    ) -> float:
        self._ensure_loaded()
        flag_def = self._flags.get(flag_key)
        if flag_def is None:
            return default
        if isinstance(flag_def, dict):
            return float(flag_def.get("value", default))
        return float(flag_def)

    async def get_object(
        self, flag_key: str, default: Any, context: EvaluationContext | None = None
    ) -> Any:
        self._ensure_loaded()
        flag_def = self._flags.get(flag_key)
        if flag_def is None:
            return default
        if isinstance(flag_def, dict) and "value" in flag_def:
            return flag_def["value"]
        return flag_def
