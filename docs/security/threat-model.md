# Threat Model — mp-commons Security Primitives

**Version:** 1.0
**Date:** 2026-02-01
**Scope:** JWT verification, API key management, encryption utilities, PII redaction

This document applies the **STRIDE** framework (Spoofing, Tampering, Repudiation,
Information Disclosure, Denial of Service, Elevation of Privilege) to the
security-related modules exported by `mp-commons`.

---

## 1. JWT Verification (`mp_commons.kernel.security.jwt`)

### Assets
- Identity claims (sub, roles, tenant_id) extracted from the token.
- The secret/public key used to verify signatures.

### STRIDE Analysis

| Threat | Category | Mitigation |
|---|---|---|
| Attacker forges a JWT with elevated `roles` | **Spoofing** | `JwtDecoder.decode()` verifies HMAC/RSA signature; rejects tokens with invalid signature. |
| `alg: none` attack — strip signature | **Spoofing** | `algorithms` parameter must be explicitly set; `none` is never in the default list. |
| Replayed expired token | **Spoofing** | `exp` claim is validated; expired tokens raise `JwtValidationError`. |
| Token contains wrong audience | **Elevation of Privilege** | `audience` parameter enforces `aud` claim; mismatch raises an error. |
| Key logged in application stdout | **Information Disclosure** | Keys are never included in log output; `JwtValidationError` messages redact token content. |
| Flood of invalid tokens | **Denial of Service** | Signature verification is O(1) for HMAC; RSA verification is ~1 ms; recommend rate-limiting at the gateway layer. |

### Residual Risk
- If the signing key is compromised, all tokens are forgeable until key rotation.
  **Mitigation**: rotate keys via the `JwtKeyRotator` and set short `exp` (≤15 min for access tokens).

---

## 2. API Key Management (`mp_commons.security.apikeys`)

### Assets
- Raw API keys (must never be stored at rest).
- Hashed API key values in the database.

### STRIDE Analysis

| Threat | Category | Mitigation |
|---|---|---|
| Attacker reads the database and recovers keys | **Information Disclosure** | Keys are hashed with argon2id (memory-hard) before storage; raw keys are never persisted. |
| Timing attack on hash comparison | **Spoofing** | `hmac.compare_digest()` is used for constant-time comparison in all verification paths. |
| Hash upgrade races (bcrypt → argon2) | **Tampering** | `ApiKeyHashUpgrade` re-hashes atomically; the old hash is only replaced after successful argon2 verification. |
| Brute-force enumeration of API keys | **Spoofing** | argon2id default parameters (t=3, m=65536, p=4) make offline brute-force infeasible. |
| API key leaked in request logs | **Information Disclosure** | `RegexPIIRedactor` patterns cover `Bearer <token>` and `apikey=<value>` patterns; enable PII redaction on all HTTP adapters. |
| Key used after revocation | **Elevation of Privilege** | Applications must check `ApiKey.revoked_at` after hash verification; `mp-commons` provides the check but enforcement is the caller's responsibility. |

### Residual Risk
- Key length: keys shorter than 32 bytes are rejected by the generator, but
  callers who supply their own keys are responsible for entropy.

---

## 3. Encryption Utilities (`mp_commons.security.encryption`)

### Assets
- Plaintext data passed to `encrypt()` / `decrypt()`.
- The symmetric encryption key.

### STRIDE Analysis

| Threat | Category | Mitigation |
|---|---|---|
| Decryption of ciphertext without key | **Information Disclosure** | AES-256-GCM with random nonce; brute-force is computationally infeasible. |
| Ciphertext manipulation | **Tampering** | GCM authentication tag detects any bit-flip; `decrypt()` raises `InvalidTag` on tampered data. |
| Nonce reuse (→ keystream reuse) | **Information Disclosure** | `os.urandom(12)` generates a fresh nonce per encryption call; nonce collision probability over 2³² calls is ~10⁻¹⁸. |
| Key material in environment variables | **Information Disclosure** | Documented best practice: load keys from Vault or AWS Secrets Manager, not from `.env` files committed to source control. |
| Unauthenticated decryption of arbitrary ciphertext | **Tampering** | GCM tag verification happens before any plaintext bytes are returned. |

### Residual Risk
- If the key leaks, all data encrypted with that key is exposed.
  **Mitigation**: implement key rotation with a `key_version` prefix in the ciphertext envelope.

---

## 4. PII Redaction (`mp_commons.security.pii`)

### Assets
- Log lines and telemetry spans that may contain PII.
- The regex patterns that identify PII.

### STRIDE Analysis

| Threat | Category | Mitigation |
|---|---|---|
| PII escapes redaction via encoding (URL-encoded CPF, etc.) | **Information Disclosure** | Fuzz tests (`T-07`) exercise base64/URL-encoded variants; patterns are updated when false negatives are found. |
| Redaction regex causes catastrophic backtracking (ReDoS) | **Denial of Service** | Patterns use possessive quantifiers or anchors where possible; `re.compile` is called once at startup. |
| False positives redact non-PII data | **Information Disclosure** (indirect — obscures debugging) | Integration and property tests verify that random strings without PII sub-patterns are not redacted. |
| Log injection via ANSI escape sequences in PII fields | **Tampering** | Structured JSON logging (`structlog`) never interprets escape sequences; raw text handlers should strip control characters. |

### Residual Risk
- Pattern coverage is not exhaustive; novel PII formats (e.g. new government ID
  schemes) may not be detected until patterns are updated.  Run `T-07` fuzz
  tests and review pattern coverage when entering new markets.

---

## 5. Webhook Signature Verification (`IncomingWebhookMiddleware`)

### Assets
- The webhook shared secret used to compute HMAC-SHA256 signatures.
- The integrity of inbound webhook payloads.

### STRIDE Analysis

| Threat | Category | Mitigation |
|---|---|---|
| Forged webhook payload | **Spoofing / Tampering** | `X-Hub-Signature-256` header is verified with `hmac.compare_digest`; requests without a valid signature are rejected with 403. |
| Replay attack (resend a previously valid request) | **Tampering** | Callers should include a timestamp in the payload and reject requests older than 5 minutes; `IncomingWebhookMiddleware` does not enforce this — application responsibility. |
| Timing attack via short-circuit string comparison | **Spoofing** | `hmac.compare_digest()` ensures constant-time comparison. |
| Secret stored in environment variable | **Information Disclosure** | Load from Vault or AWS Secrets Manager; never commit to source control. |

---

## 6. Summary of Key Security Properties

| Primitive | Algorithm / Standard | Key Rotation Support |
|---|---|---|
| JWT verification | HS256 / RS256 (configurable) | Yes — `JwtKeyRotator` |
| API key hashing | argon2id | Yes — `ApiKeyHashUpgrade` |
| Encryption | AES-256-GCM | Via key-version prefix (application responsibility) |
| Webhook verification | HMAC-SHA256 | Via shared-secret rotation |
| PII redaction | Regex patterns | Pattern update via library upgrade |
