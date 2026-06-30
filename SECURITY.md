# Security Policy

## Supported Versions

Only the latest release of **Gunther API** receives security fixes.

## Reporting a Vulnerability

Please do **not** open a public GitHub issue for security vulnerabilities.

Send a private report to **** via GitHub's
[private security advisory](../../security/advisories/new) feature or by email.

Include:
- A description of the vulnerability
- Steps to reproduce
- Potential impact
- Any suggested mitigations

We aim to respond within **72 hours** and release a patch within **7 days** for critical issues.

## Security Measures in This Project

- Dependencies scanned weekly by Renovate
- Semgrep SAST on every commit (via pre-commit)
- Bandit security linter in CI
- detect-secrets prevents credential leakage at commit time
- Sentry for runtime error monitoring (if configured)
