"""Config settings – Settings base class."""
from __future__ import annotations

import dataclasses


@dataclasses.dataclass
class Settings:
    """Base class for 12-factor settings."""

    _prefix: dataclasses.ClassVar[str] = ""

    def __post_init__(self) -> None:
        self._validate()

    def _validate(self) -> None:
        """Override to add cross-field validation."""


__all__ = ["Settings"]
