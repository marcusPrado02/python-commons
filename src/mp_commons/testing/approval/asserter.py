"""Approval test asserters."""
from __future__ import annotations

import difflib
import html as _html_module
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

__all__ = [
    "ApprovalAsserter",
    "ApprovalError",
    "HtmlApprovalAsserter",
    "JsonApprovalAsserter",
]


class ApprovalError(AssertionError):
    """Raised when a received value does not match the approved baseline."""


class ApprovalAsserter:
    """Write *received* text to a `.received.txt` file and compare with `.approved.txt`.

    On first run (no approved file) the received file is written and the test fails,
    prompting the developer to inspect and rename it to `.approved.txt`.

    Pass ``approve=True`` to automatically promote received → approved (batch approve).
    """

    def __init__(
        self,
        directory: str | Path = "tests/__approvals__",
        approve: bool = False,
    ) -> None:
        self._dir = Path(directory)
        self._approve = approve

    def _received_path(self, name: str) -> Path:
        safe = name.replace("/", "_").replace("\\", "_")
        return self._dir / f"{safe}.received.txt"

    def _approved_path(self, name: str) -> Path:
        safe = name.replace("/", "_").replace("\\", "_")
        return self._dir / f"{safe}.approved.txt"

    def _normalise(self, text: str) -> str:
        return text

    def approve(self, received: str, test_name: str) -> None:
        """Assert *received* matches the approved baseline for *test_name*."""
        normalised = self._normalise(received)
        self._dir.mkdir(parents=True, exist_ok=True)
        received_path = self._received_path(test_name)
        received_path.write_text(normalised, encoding="utf-8")

        if self._approve:
            self._approved_path(test_name).write_text(normalised, encoding="utf-8")
            return

        approved_path = self._approved_path(test_name)
        if not approved_path.exists():
            raise ApprovalError(
                f"No approved file for {test_name!r}. "
                f"Inspect {received_path} and copy to {approved_path} to approve."
            )

        approved = approved_path.read_text(encoding="utf-8")
        if approved == normalised:
            received_path.unlink(missing_ok=True)
            return

        diff = "\n".join(
            difflib.unified_diff(
                approved.splitlines(),
                normalised.splitlines(),
                fromfile=str(approved_path),
                tofile=str(received_path),
                lineterm="",
            )
        )
        raise ApprovalError(
            f"Approval mismatch for {test_name!r}:\n{diff}"
        )

    def approved_file_exists(self, test_name: str) -> bool:
        return self._approved_path(test_name).exists()

    def received_file_exists(self, test_name: str) -> bool:
        return self._received_path(test_name).exists()


class _StripTagsParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def get_text(self) -> str:
        return "".join(self._parts)


# Regex to strip ISO-8601 / common timestamp patterns for normalisation
_TIMESTAMP_RE = re.compile(
    r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?"
)


def _pretty_html(raw: str) -> str:
    """Re-indent HTML using stdlib html.parser for deterministic comparison."""
    import html as _html

    # Unescape entities then re-format with consistent indentation via minidom
    try:
        from xml.dom.minidom import parseString

        # Wrap in a single root to allow minidom to parse HTML fragments
        wrapped = f"<root>{raw}</root>"
        dom = parseString(wrapped)
        pretty = dom.toprettyxml(indent="  ")
        # Remove the <?xml ...?> header and the artificial <root> wrapper
        lines = pretty.splitlines()[1:]  # drop xml declaration
        # Remove wrapping <root> and </root>
        if lines and lines[0].strip() == "<root>":
            lines = lines[1:]
        if lines and lines[-1].strip() == "</root>":
            lines = lines[:-1]
        # Drop whitespace-only lines produced by toprettyxml for text nodes
        lines = [ln for ln in lines if ln.strip()]
        return "\n".join(lines)
    except Exception:
        return raw


class HtmlApprovalAsserter(ApprovalAsserter):
    """Approval asserter that normalises HTML and strips dynamic timestamps."""

    def _normalise(self, text: str) -> str:
        pretty = _pretty_html(text)
        # Strip timestamps so they don't cause spurious diffs
        return _TIMESTAMP_RE.sub("__TIMESTAMP__", pretty)


class JsonApprovalAsserter(ApprovalAsserter):
    """Approval asserter that normalises JSON (sorted keys, consistent formatting)."""

    def _normalise(self, text: str) -> str:
        try:
            obj = json.loads(text)
            return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False)
        except json.JSONDecodeError:
            return text
