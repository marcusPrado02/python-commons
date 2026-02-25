from __future__ import annotations

import logging
from typing import Any

from mp_commons.application.masking.masker import DataMasker
from mp_commons.application.masking.rules import MaskingRule

__all__ = ["PiiLogFilter"]


class PiiLogFilter(logging.Filter):
    """Applies DataMasker to log record msg and args before emission."""

    def __init__(self, rules: list[MaskingRule], name: str = "") -> None:
        super().__init__(name)
        self._masker = DataMasker()
        self._rules = rules

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        if isinstance(record.msg, dict):
            record.msg = self._masker.mask(record.msg, self._rules)
        if isinstance(record.args, dict):
            record.args = self._masker.mask(record.args, self._rules)  # type: ignore[assignment]
        elif isinstance(record.args, (list, tuple)):
            masked: list[Any] = []
            for arg in record.args:
                if isinstance(arg, dict):
                    masked.append(self._masker.mask(arg, self._rules))
                else:
                    masked.append(arg)
            record.args = tuple(masked)
        return True
