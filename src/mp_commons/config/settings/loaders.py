"""Config settings – EnvSettingsLoader, DotenvSettingsLoader."""
from __future__ import annotations

import abc
import dataclasses
import os
from typing import Any, TypeVar

from mp_commons.config.settings.base import Settings
from mp_commons.config.validation import ConfigError, MissingRequiredSettingError

T = TypeVar("T", bound=Settings)


class SettingsLoader(abc.ABC):
    """Port: load settings from an external source."""

    @abc.abstractmethod
    def load(self, settings_class: type[T]) -> T: ...


class EnvSettingsLoader(SettingsLoader):
    """Load settings from OS environment variables."""

    def load(self, settings_class: type[T]) -> T:
        prefix = getattr(settings_class, "_prefix", "").upper()
        kwargs: dict[str, Any] = {}

        for field in dataclasses.fields(settings_class):  # type: ignore[arg-type]
            env_key = f"{prefix}_{field.name}".upper().lstrip("_")
            raw = os.environ.get(env_key)

            if raw is None:
                if (
                    field.default is dataclasses.MISSING
                    and field.default_factory is dataclasses.MISSING  # type: ignore[misc]
                ):
                    raise MissingRequiredSettingError(env_key)
                continue

            kwargs[field.name] = self._coerce(raw, field.type)

        try:
            return settings_class(**kwargs)
        except Exception as exc:
            raise ConfigError(f"Failed to load settings: {exc}") from exc

    def _coerce(self, value: str, type_hint: Any) -> Any:  # noqa: PLR0911
        origin = getattr(type_hint, "__origin__", None)
        if type_hint is bool or type_hint == "bool":
            return value.lower() in ("1", "true", "yes", "on")
        if type_hint is int or type_hint == "int":
            return int(value)
        if type_hint is float or type_hint == "float":
            return float(value)
        if origin is list:
            return [v.strip() for v in value.split(",") if v.strip()]
        return value


class DotenvSettingsLoader(SettingsLoader):
    """Load settings from a ``.env`` file then fall back to ``EnvSettingsLoader``."""

    def __init__(self, env_file: str = ".env", override: bool = False) -> None:
        self._env_file = env_file
        self._override = override

    def load(self, settings_class: type[T]) -> T:
        try:
            from dotenv import load_dotenv  # type: ignore[import-untyped]
            load_dotenv(self._env_file, override=self._override)
        except ImportError as exc:
            raise ImportError("Install 'python-dotenv' to use DotenvSettingsLoader") from exc
        return EnvSettingsLoader().load(settings_class)


__all__ = ["DotenvSettingsLoader", "EnvSettingsLoader", "SettingsLoader"]
