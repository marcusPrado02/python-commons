"""Locale value object, context, translator, middleware, and TranslatedError mixin."""
from __future__ import annotations

import contextvars
import re
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncGenerator

__all__ = [
    "Locale",
    "LocaleContext",
    "LocaleMiddleware",
    "TranslatedError",
    "Translator",
]


# ---------------------------------------------------------------------------
# Locale value object
# ---------------------------------------------------------------------------

_BCP47_RE = re.compile(
    r"^(?P<lang>[a-zA-Z]{2,8})"
    r"(?:[_-](?P<territory>[a-zA-Z]{2}|\d{3}))?"
    r"(?:[_-].+)?$"
)


@dataclass(frozen=True)
class Locale:
    """Immutable BCP-47 locale value object (e.g. ``en``, ``pt-BR``)."""

    language: str
    territory: str | None = None

    def __str__(self) -> str:
        if self.territory:
            return f"{self.language}-{self.territory}"
        return self.language

    @classmethod
    def parse(cls, tag: str) -> Locale:
        """Parse a BCP-47 tag like ``"pt-BR"`` or ``"en"``."""
        m = _BCP47_RE.match(tag.strip())
        if not m:
            raise ValueError(f"Invalid BCP-47 locale tag: {tag!r}")
        return cls(
            language=m.group("lang").lower(),
            territory=(m.group("territory") or "").upper() or None,
        )

    @classmethod
    def default(cls) -> Locale:
        return cls(language="en")

    def babel_str(self) -> str:
        """Return Babel-compatible locale string (underscore separator)."""
        if self.territory:
            return f"{self.language}_{self.territory}"
        return self.language


# ---------------------------------------------------------------------------
# LocaleContext — contextvars-backed
# ---------------------------------------------------------------------------

_locale_var: contextvars.ContextVar[Locale] = contextvars.ContextVar(
    "locale", default=Locale.default()
)


class LocaleContext:
    """Access and mutate the current request locale via a ContextVar."""

    @staticmethod
    def get() -> Locale:
        return _locale_var.get()

    @staticmethod
    def set(locale: Locale) -> contextvars.Token[Locale]:
        return _locale_var.set(locale)

    @staticmethod
    def reset(token: contextvars.Token[Locale]) -> None:
        _locale_var.reset(token)

    @staticmethod
    @asynccontextmanager
    async def scoped(locale: Locale) -> AsyncGenerator[Locale, None]:
        """Async context manager that sets locale for the duration of the block."""
        token = _locale_var.set(locale)
        try:
            yield locale
        finally:
            _locale_var.reset(token)


# ---------------------------------------------------------------------------
# Translator — Babel-backed .po/.mo loader
# ---------------------------------------------------------------------------

def _require_babel() -> Any:
    try:
        import babel  # noqa: F401
        from babel.support import Translations
        return Translations
    except ImportError as exc:
        raise ImportError("pip install babel") from exc


class Translator:
    """Translate message keys using Babel .po/.mo catalogues.

    *locale_dir* should contain sub-directories like ``en/LC_MESSAGES/messages.mo``.
    If *locale_dir* is *None* or the translation file is absent the key is returned
    as-is (identity fallback).
    """

    def __init__(
        self,
        locale_dir: str | Path | None = None,
        domain: str = "messages",
        supported_locales: list[str] | None = None,
    ) -> None:
        self._locale_dir = Path(locale_dir) if locale_dir else None
        self._domain = domain
        self._supported = [Locale.parse(l) for l in (supported_locales or [])]
        self._cache: dict[str, Any] = {}

    def _get_translations(self, locale: Locale) -> Any:
        key = locale.babel_str()
        if key in self._cache:
            return self._cache[key]
        if self._locale_dir is None:
            return None
        Translations = _require_babel()
        translation_path = self._locale_dir / locale.babel_str() / "LC_MESSAGES" / f"{self._domain}.mo"
        if not translation_path.exists():
            # Try language only
            translation_path = self._locale_dir / locale.language / "LC_MESSAGES" / f"{self._domain}.mo"
        if not translation_path.exists():
            self._cache[key] = None
            return None
        trans = Translations.load(
            dirname=str(self._locale_dir),
            locales=[locale.babel_str()],
            domain=self._domain,
        )
        self._cache[key] = trans
        return trans

    def translate(
        self,
        key: str,
        locale: Locale | None = None,
        **kwargs: Any,
    ) -> str:
        effective_locale = locale or LocaleContext.get()
        trans = self._get_translations(effective_locale)
        if trans is None:
            text = key
        else:
            text = trans.ugettext(key) if hasattr(trans, "ugettext") else trans.gettext(key)
        if kwargs:
            try:
                text = text.format(**kwargs)
            except (KeyError, ValueError):
                pass
        return text

    def negotiate(self, accept_language: str) -> Locale:
        """Pick the best supported locale from an Accept-Language header value."""
        if not self._supported:
            return LocaleContext.get()
        # Parse Accept-Language header: "pt-BR,pt;q=0.9,en;q=0.8"
        candidates: list[tuple[float, str]] = []
        for part in accept_language.split(","):
            part = part.strip()
            if ";q=" in part:
                lang, q_str = part.split(";q=", 1)
                try:
                    q = float(q_str)
                except ValueError:
                    q = 0.0
            else:
                lang = part
                q = 1.0
            candidates.append((q, lang.strip()))
        candidates.sort(reverse=True)
        for _, lang_tag in candidates:
            try:
                requested = Locale.parse(lang_tag)
            except ValueError:
                continue
            # Exact match
            for supported in self._supported:
                if supported == requested:
                    return supported
            # Language-only match
            for supported in self._supported:
                if supported.language == requested.language:
                    return supported
        return self._supported[0]


# ---------------------------------------------------------------------------
# LocaleMiddleware — FastAPI / Starlette
# ---------------------------------------------------------------------------

class LocaleMiddleware:
    """ASGI middleware that reads Accept-Language and sets LocaleContext."""

    def __init__(self, app: Any, translator: Translator) -> None:
        self._app = app
        self._translator = translator

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] == "http":
            headers = dict(scope.get("headers", []))
            accept = headers.get(b"accept-language", b"").decode("latin-1")
            if accept:
                locale = self._translator.negotiate(accept)
            else:
                locale = Locale.default()
            token = LocaleContext.set(locale)
            try:
                await self._app(scope, receive, send)
            finally:
                LocaleContext.reset(token)
        else:
            await self._app(scope, receive, send)


# ---------------------------------------------------------------------------
# TranslatedError mixin
# ---------------------------------------------------------------------------

class TranslatedError(Exception):
    """Exception mixin whose message can be localised on demand."""

    message_key: str = ""

    def __init__(self, message_key: str | None = None, **context: Any) -> None:
        self.message_key = message_key or self.__class__.message_key
        self.context = context
        super().__init__(self.message_key)

    def localise(self, translator: Translator, locale: Locale | None = None) -> str:
        """Return the translated error message for *locale*."""
        return translator.translate(self.message_key, locale=locale, **self.context)
