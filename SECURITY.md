# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | ✅ Active  |

Only the latest patch release of the current minor version receives security fixes.

## Reporting a Vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.**

Report security issues privately via GitHub's
[Security Advisories](https://github.com/marcusPrado02/python-commons/security/advisories/new)
feature (*Security → Advisories → New draft security advisory*).

Include the following in your report:

- A description of the vulnerability and its potential impact
- Steps to reproduce or a minimal proof-of-concept
- Affected versions
- Any suggested mitigations, if known

### Response timeline

| Step | Target |
|------|--------|
| Initial acknowledgement | ≤ 2 business days |
| Triage and severity assessment | ≤ 5 business days |
| Patch release (Critical/High) | ≤ 14 calendar days |
| Patch release (Medium/Low) | Next scheduled release |

## Disclosure Policy

We follow **responsible disclosure**:

1. Reporter submits vulnerability privately.
2. Maintainers triage, reproduce, and develop a fix.
3. A new patch version is released with the fix.
4. A GitHub Security Advisory (CVE) is published simultaneously.
5. Credit is given to the reporter unless they prefer to remain anonymous.

## Scope

This policy covers the `mp-commons` Python library and its published PyPI
package (`mp-commons`). It does **not** cover third-party adapters or
consumers of this library — those are the responsibility of the respective
project maintainers.

## Contact

For non-security issues use [GitHub Issues](https://github.com/marcusPrado02/python-commons/issues).  
For urgent security matters email the maintainer directly (see git log for contact).
