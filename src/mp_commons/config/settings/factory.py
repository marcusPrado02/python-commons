"""Config settings – SettingsFactory."""
from __future__ import annotations

import dataclasses
from typing import Any, Sequence, TypeVar

from mp_commons.config.settings.base import Settings
from mp_commons.config.settings.loaders import SettingsLoader
from mp_commons.config.validation.errors import (
    ConfigError,
    MissingRequiredSettingError,
)

T = TypeVar("T", bound=Settings)


class SettingsFactory:
    """Merge outputs from multiple loaders, apply overrides, and construct
    a settings dataclass in one step.

    Loaders are applied in order; later loaders override earlier ones for
    overlapping fields.  *overrides* (if provided) take the highest priority.
    Loaders that raise exceptions are silently skipped so that the remaining
    loaders may still contribute values.
    """

    @staticmethod
    def create(
        settings_cls: type[T],
        loaders: Sequence[SettingsLoader] | None = None,
        overrides: dict[str, Any] | None = None,
    ) -> T:
        """
        Parameters
        ----------
        settings_cls:
            The :class:`~mp_commons.config.settings.base.Settings` subclass to
            construct.
        loaders:
            Ordered sequence of :class:`~mp_commons.config.settings.loaders.\
SettingsLoader` instances.  Later loaders win on field conflicts.
        overrides:
            Explicit key-value pairs applied after all loaders, useful for
            tests and local development.

        Returns
        -------
        T
            Populated settings instance.

        Raises
        ------
        MissingRequiredSettingError
            When a required field (no default) is absent after all sources
            have been merged.
        InvalidSettingValueError
            When a value is present but cannot be coerced into the declared
            field type.
        ConfigError
            On any other construction failure.
        """
        merged: dict[str, Any] = {}

        for loader in loaders or []:
            try:
                instance = loader.load(settings_cls)
                for field in dataclasses.fields(instance):  # type: ignore[arg-type]
                    merged[field.name] = getattr(instance, field.name)
            except Exception:  # noqa: BLE001 – skip failing loaders
                pass

        if overrides:
            merged.update(overrides)

        # Validate all required fields are present before construction.
        for field in dataclasses.fields(settings_cls):  # type: ignore[arg-type]
            if field.name in merged:
                continue
            if (
                field.default is dataclasses.MISSING
                and field.default_factory is dataclasses.MISSING  # type: ignore[misc]
            ):
                raise MissingRequiredSettingError(field.name)

        try:
            return settings_cls(**merged)
        except Exception as exc:
            raise ConfigError(f"Failed to construct {settings_cls.__name__}: {exc}") from exc


__all__ = ["SettingsFactory"]
