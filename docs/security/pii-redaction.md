# PII Redaction Policy

`mp-commons` provides automatic PII redaction at two layers:

1. **Log-level** — `SensitiveFieldsFilter` scrubs log record `extra` dicts
   and nested structures before they reach any log handler.
2. **Application-level** — `PIIRedactor` protocol allows custom redactors to
   be injected into use-case pipelines and serialisation helpers.

---

## Default Sensitive Fields

```python
DEFAULT_SENSITIVE_FIELDS = frozenset({
    "password", "passwd", "secret", "token", "api_key",
    "access_token", "refresh_token", "authorization",
    "credit_card", "card_number", "cvv", "ssn",
    "cpf", "cnpj", "rg",
    "email",   # may be toggled off per-service
    "phone", "phone_number",
})
```

## Adding Custom Fields

```python
from mp_commons.observability.logging import SensitiveFieldsFilter

flt = SensitiveFieldsFilter(extra_fields={"national_id", "iban"})
```

## Redaction Depth

`redact_deep(obj)` recursively traverses `dict`, `list`, and scalar values:

- Dict key matching a sensitive field → value replaced with `"[REDACTED]"`
- Nested dicts and lists are traversed recursively
- Non-dict / non-list scalars are returned unchanged

## Compliance Notes

- LGPD (Brazil): `cpf`, `cnpj`, `rg` are always in the default set.
- GDPR: `email` is in the default set but can be opted out when email is a
  non-personal business identifier.
- PCI-DSS: `credit_card`, `card_number`, `cvv` are always redacted.

## What Is NOT Redacted

- Correlation IDs, trace IDs, span IDs — these are operational identifiers
  without PII.
- Tenant IDs — these are business identifiers, not personal data.
- User IDs — opaque identifiers. The mapping to actual personal data lives
  only in the identity service.
