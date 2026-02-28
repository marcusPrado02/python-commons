"""Unit tests for §100 i18n — Locale, LocaleContext, Translator, TranslatedError."""
import asyncio
import pathlib
import tempfile

import pytest

from mp_commons.application.i18n import (
    Locale,
    LocaleContext,
    Translator,
    TranslatedError,
)


# ---------------------------------------------------------------------------
# Locale.parse
# ---------------------------------------------------------------------------

def test_locale_parse_language_and_territory():
    loc = Locale.parse("pt-BR")
    assert loc.language == "pt"
    assert loc.territory == "BR"


def test_locale_parse_language_only():
    loc = Locale.parse("en")
    assert loc.language == "en"
    assert loc.territory is None


def test_locale_parse_underscore_variant():
    loc = Locale.parse("pt_BR")
    assert loc.language == "pt"
    assert loc.territory == "BR"


def test_locale_parse_case_insensitive():
    loc = Locale.parse("EN-us")
    assert loc.language == "en"
    assert loc.territory == "US"


def test_locale_parse_invalid_raises():
    with pytest.raises(ValueError):
        Locale.parse("not valid locale!!")


def test_locale_parse_empty_raises():
    with pytest.raises(ValueError):
        Locale.parse("")


# ---------------------------------------------------------------------------
# Locale str / babel_str
# ---------------------------------------------------------------------------

def test_locale_str_with_territory():
    loc = Locale("pt", "BR")
    assert str(loc) == "pt-BR"


def test_locale_str_without_territory():
    loc = Locale("en", None)
    assert str(loc) == "en"


def test_locale_babel_str_with_territory():
    loc = Locale("pt", "BR")
    assert loc.babel_str() == "pt_BR"


def test_locale_babel_str_without_territory():
    loc = Locale("en", None)
    assert loc.babel_str() == "en"


def test_locale_default():
    loc = Locale.default()
    assert loc.language == "en"
    assert loc.territory is None


# ---------------------------------------------------------------------------
# LocaleContext — sync
# ---------------------------------------------------------------------------

def test_locale_context_default_is_en():
    # Each call to get() should return a sensible default (en)
    loc = LocaleContext.get()
    assert loc.language == "en"


def test_locale_context_set_and_reset():
    token = LocaleContext.set(Locale.parse("fr"))
    try:
        assert LocaleContext.get().language == "fr"
    finally:
        LocaleContext.reset(token)
    assert LocaleContext.get().language == "en"


def test_locale_context_scoped_async_cm():
    async def run():
        initial = LocaleContext.get()
        async with LocaleContext.scoped(Locale.parse("de")) as loc:
            assert loc.language == "de"
            assert LocaleContext.get().language == "de"
        # After exiting the CM, context should be restored
        assert LocaleContext.get().language == initial.language

    asyncio.run(run())


def test_locale_context_scoped_restores_on_exception():
    async def run():
        initial_lang = LocaleContext.get().language
        try:
            async with LocaleContext.scoped(Locale.parse("ja")):
                raise ValueError("oops")
        except ValueError:
            pass
        assert LocaleContext.get().language == initial_lang

    asyncio.run(run())


# ---------------------------------------------------------------------------
# Translator — identity fallback (no locale dir)
# ---------------------------------------------------------------------------

def test_translator_returns_key_when_no_translations(tmp_path):
    t = Translator(
        locale_dir=str(tmp_path),
        domain="messages",
        supported_locales=["en"],
    )
    result = t.translate("welcome.message", locale=Locale.parse("en"))
    assert result == "welcome.message"


def test_translator_interpolates_kwargs(tmp_path):
    t = Translator(
        locale_dir=str(tmp_path),
        domain="messages",
        supported_locales=["en"],
    )
    # When translation is identity (key), kwargs format is applied to key
    result = t.translate("hello {name}", locale=Locale.parse("en"), name="World")
    assert result == "hello World"


# ---------------------------------------------------------------------------
# Translator.negotiate
# ---------------------------------------------------------------------------

def test_translator_negotiate_exact_match(tmp_path):
    t = Translator(
        locale_dir=str(tmp_path),
        domain="messages",
        supported_locales=["en", "pt-BR"],
    )
    loc = t.negotiate("pt-BR,pt;q=0.9,en;q=0.8")
    assert loc.language == "pt"
    assert loc.territory == "BR"


def test_translator_negotiate_language_only_fallback(tmp_path):
    t = Translator(
        locale_dir=str(tmp_path),
        domain="messages",
        supported_locales=["en", "pt"],
    )
    loc = t.negotiate("pt-BR,pt;q=0.9,en;q=0.8")
    assert loc.language == "pt"


def test_translator_negotiate_falls_back_to_first_supported(tmp_path):
    t = Translator(
        locale_dir=str(tmp_path),
        domain="messages",
        supported_locales=["en", "fr"],
    )
    loc = t.negotiate("de-DE,de;q=0.9")
    assert loc.language == "en"


def test_translator_negotiate_empty_header(tmp_path):
    t = Translator(
        locale_dir=str(tmp_path),
        domain="messages",
        supported_locales=["en", "fr"],
    )
    loc = t.negotiate("")
    assert loc.language == "en"


# ---------------------------------------------------------------------------
# TranslatedError
# ---------------------------------------------------------------------------

def test_translated_error_localise_returns_key_without_translations(tmp_path):
    class MyError(TranslatedError):
        message_key = "error.not_found"

    translator = Translator(
        locale_dir=str(tmp_path),
        domain="messages",
        supported_locales=["en"],
    )
    err = MyError()
    result = err.localise(translator, locale=Locale.parse("en"))
    assert result == "error.not_found"


def test_translated_error_localise_interpolates_context(tmp_path):
    class ResourceError(TranslatedError):
        message_key = "error.resource {resource}"

    translator = Translator(
        locale_dir=str(tmp_path),
        domain="messages",
        supported_locales=["en"],
    )
    err = ResourceError(resource="order")
    result = err.localise(translator, locale=Locale.parse("en"))
    assert result == "error.resource order"


def test_translated_error_is_exception():
    class MyError(TranslatedError):
        message_key = "some.error"

    err = MyError()
    assert isinstance(err, Exception)
