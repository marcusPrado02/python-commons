"""Application email – Jinja2EmailRenderer (optional 'jinja2' extra)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from mp_commons.application.email.message import EmailMessage

__all__ = ["Jinja2EmailRenderer"]


def _require_jinja2() -> Any:  # pragma: no cover
    try:
        import jinja2  # noqa: PLC0415
        return jinja2
    except ImportError as exc:
        raise ImportError(
            "Jinja2 is required for email rendering. "
            "Install it with: pip install jinja2"
        ) from exc


class Jinja2EmailRenderer:
    """Renders EmailMessage objects from Jinja2 HTML (and optional text) templates.

    Template naming convention:
      - ``{template_name}.html.j2``  — HTML body
      - ``{template_name}.txt.j2``   — plain-text body (optional)
      - ``{template_name}.subject.j2`` — subject line (optional, falls back to
        the ``subject`` kwarg passed to :meth:`render`)
    """

    def __init__(self, templates_dir: str | Path) -> None:
        jinja2 = _require_jinja2()
        self._env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(templates_dir)),
            autoescape=jinja2.select_autoescape(["html"]),
        )

    def render(
        self,
        template_name: str,
        context: dict[str, Any],
        *,
        to: list[str],
        subject: str | None = None,
        cc: list[str] | None = None,
        bcc: list[str] | None = None,
        reply_to: str | None = None,
    ) -> EmailMessage:
        html_body = self._env.get_template(f"{template_name}.html.j2").render(**context)

        text_body: str | None = None
        try:
            text_body = self._env.get_template(f"{template_name}.txt.j2").render(**context)
        except Exception:  # noqa: BLE001
            pass

        resolved_subject = subject or ""
        try:
            resolved_subject = self._env.get_template(f"{template_name}.subject.j2").render(**context).strip()
        except Exception:  # noqa: BLE001
            pass

        return EmailMessage(
            to=to,
            subject=resolved_subject,
            html_body=html_body,
            text_body=text_body,
            cc=cc or [],
            bcc=bcc or [],
            reply_to=reply_to,
        )
