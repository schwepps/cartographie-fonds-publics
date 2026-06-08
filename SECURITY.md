# Security Policy

## Reporting a vulnerability
Please **do not** open a public issue for security problems.
Report privately via GitHub: open the repository's **Security** tab → **Report a vulnerability**
(GitHub [private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)).
Include details and steps to reproduce. We aim to acknowledge within 5 business days.

## Scope & data
- This project only ingests **public open data** (Licence Ouverte / Etalab 2.0).
- No secrets are committed. Credentials live in `.env` (gitignored) or CI secrets.
- Raw data snapshots are never committed (see `.gitignore`).

## Supported versions
The `main` branch receives security fixes. Releases are tagged with SemVer.
