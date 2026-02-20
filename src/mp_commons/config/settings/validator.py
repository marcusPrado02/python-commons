"""Config settings – SettingsValidator."""
from __future__ import annotations

import dataclasses

from mp_commons.config.settings.base import Settings


class SettingsValidator:
    """Validate a populated settings instance."""

    def validate(self, settings: Settings) -> list[str]:
        """Return a list of validation error messages."""
        errors: list[str] = []
        for field in dataclasses.fields(settings):
            value = getattr(settings, field.name)
            if value is None and field.default is dataclasses.MISSING:
                errors.append(f"{field.name} is required but None")
        return errors


__all__ = ["SettingsValidator"]
