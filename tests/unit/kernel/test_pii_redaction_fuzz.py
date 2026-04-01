"""Hypothesis fuzz tests for RegexPIIRedactor (T-07)."""
from __future__ import annotations

from hypothesis import given, assume, settings
from hypothesis import strategies as st

from mp_commons.kernel.security.pii import RegexPIIRedactor, DEFAULT_SENSITIVE_FIELDS


redactor = RegexPIIRedactor()

# ---------------------------------------------------------------------------
# Strategies for PII-containing strings
# ---------------------------------------------------------------------------

_SAFE_TEXT = st.text(
    alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd", "Zs")),
    max_size=50,
)

EMAIL_LOCAL = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789._+-",
    min_size=1,
    max_size=20,
).filter(lambda s: s[0] not in ".+-" and s[-1] not in ".+-")

EMAIL_DOMAIN = st.sampled_from([
    "example.com", "test.org", "mail.net", "foo.io", "company.co.uk"
])


@st.composite
def email_in_text(draw) -> str:
    prefix = draw(_SAFE_TEXT)
    local = draw(EMAIL_LOCAL)
    domain = draw(EMAIL_DOMAIN)
    suffix = draw(_SAFE_TEXT)
    return f"{prefix} {local}@{domain} {suffix}"


@st.composite
def cpf_in_text(draw) -> str:
    d1 = draw(st.integers(min_value=0, max_value=999))
    d2 = draw(st.integers(min_value=0, max_value=999))
    d3 = draw(st.integers(min_value=0, max_value=999))
    d4 = draw(st.integers(min_value=0, max_value=99))
    sep = draw(st.sampled_from(["-", "/"]))
    prefix = draw(_SAFE_TEXT)
    suffix = draw(_SAFE_TEXT)
    cpf = f"{d1:03d}.{d2:03d}.{d3:03d}{sep}{d4:02d}"
    return f"{prefix} {cpf} {suffix}"


# ---------------------------------------------------------------------------
# Fuzz: email always redacted
# ---------------------------------------------------------------------------


@given(email_in_text())
def test_email_is_always_redacted(text: str) -> None:
    """Any string containing an email pattern must get [EMAIL] substituted."""
    result = redactor._redact_text(text)
    assert "@" not in result, f"Email not redacted in: {text!r} → {result!r}"


@given(email_in_text())
def test_email_replaced_with_marker(text: str) -> None:
    result = redactor._redact_text(text)
    assert "[EMAIL]" in result


# ---------------------------------------------------------------------------
# Fuzz: CPF always redacted
# ---------------------------------------------------------------------------


@given(cpf_in_text())
def test_cpf_is_always_redacted(text: str) -> None:
    """Any string containing a CPF pattern (000.000.000-00) must be redacted."""
    result = redactor._redact_text(text)
    assert "[CPF]" in result, f"CPF not redacted in: {text!r} → {result!r}"


# ---------------------------------------------------------------------------
# Fuzz: sensitive dict keys always masked
# ---------------------------------------------------------------------------


@given(
    st.sampled_from(sorted(DEFAULT_SENSITIVE_FIELDS)),
    st.text(max_size=100),
)
def test_sensitive_key_always_masked(key: str, value: str) -> None:
    data = {key: value}
    result = redactor.redact(data)
    assert result[key] == "***"


@given(
    st.sampled_from(sorted(DEFAULT_SENSITIVE_FIELDS)),
    st.text(max_size=100),
)
def test_sensitive_key_uppercase_masked(key: str, value: str) -> None:
    """Key matching is case-insensitive."""
    data = {key.upper(): value}
    result = redactor.redact(data)
    assert result[key.upper()] == "***"


# ---------------------------------------------------------------------------
# Fuzz: non-PII strings are unchanged (identity on safe strings)
# ---------------------------------------------------------------------------


@given(st.text(alphabet="abcdefghijklmnopqrstuvwxyz ", max_size=100))
def test_clean_text_unchanged(text: str) -> None:
    """Text with no PII patterns passes through unchanged."""
    result = redactor._redact_text(text)
    assert result == text


# ---------------------------------------------------------------------------
# Fuzz: nested dict redaction
# ---------------------------------------------------------------------------


@given(
    st.sampled_from(sorted(DEFAULT_SENSITIVE_FIELDS)),
    st.text(max_size=50),
    st.text(max_size=50),
)
def test_nested_sensitive_key_masked(key: str, outer_key: str, value: str) -> None:
    assume(outer_key not in DEFAULT_SENSITIVE_FIELDS)
    assume(outer_key.lower() not in DEFAULT_SENSITIVE_FIELDS)
    data = {outer_key: {key: value}}
    result = redactor.redact(data)
    assert result[outer_key][key] == "***"


# ---------------------------------------------------------------------------
# Fuzz: redaction is idempotent (already-redacted text stays clean)
# ---------------------------------------------------------------------------


@given(email_in_text())
def test_redaction_idempotent(text: str) -> None:
    """Applying redact twice gives the same result as once."""
    once = redactor._redact_text(text)
    twice = redactor._redact_text(once)
    assert once == twice
