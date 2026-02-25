"""Application files – FileValidator."""
from __future__ import annotations

from dataclasses import dataclass, field

from mp_commons.application.files.upload import UploadedFile

__all__ = ["FileValidationError", "FileValidator", "ValidationResult"]


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    errors: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def ok(cls) -> "ValidationResult":
        return cls(valid=True, errors=())

    @classmethod
    def fail(cls, *errors: str) -> "ValidationResult":
        return cls(valid=False, errors=errors)


class FileValidationError(ValueError):
    """Raised by FileValidator when a file fails validation."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


class FileValidator:
    """Validates uploaded files against size and MIME-type constraints."""

    def __init__(
        self,
        max_size_bytes: int | None = None,
        allowed_content_types: set[str] | None = None,
    ) -> None:
        self.max_size_bytes = max_size_bytes
        self.allowed_content_types = allowed_content_types

    def validate(self, file: UploadedFile) -> ValidationResult:
        errors: list[str] = []
        if self.max_size_bytes is not None and file.size_bytes > self.max_size_bytes:
            errors.append(
                f"File size {file.size_bytes} bytes exceeds maximum of {self.max_size_bytes} bytes"
            )
        if (
            self.allowed_content_types is not None
            and file.content_type not in self.allowed_content_types
        ):
            allowed = ", ".join(sorted(self.allowed_content_types))
            errors.append(
                f"Content type '{file.content_type}' is not allowed. Allowed: {allowed}"
            )
        if errors:
            return ValidationResult.fail(*errors)
        return ValidationResult.ok()

    def validate_or_raise(self, file: UploadedFile) -> None:
        result = self.validate(file)
        if not result.valid:
            raise FileValidationError(list(result.errors))
