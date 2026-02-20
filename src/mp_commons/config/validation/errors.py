"""Config validation errors."""
from mp_commons.kernel.errors import ApplicationError


class ConfigError(ApplicationError):
    """Raised when configuration is invalid or loading failed."""
    default_code = "config_error"


class MissingRequiredSettingError(ConfigError):
    """A required environment variable / setting is absent."""
    default_code = "missing_required_setting"

    def __init__(self, setting_name: str) -> None:
        super().__init__(f"Required setting '{setting_name}' is missing")
        self.setting_name = setting_name


__all__ = ["ConfigError", "MissingRequiredSettingError"]
