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

## Automated security tooling
- **Secret scanning** — [gitleaks](https://github.com/gitleaks/gitleaks) runs as a `pre-commit`
  hook (blocks secrets locally) **and** in CI (`secrets` job in `ci.yml`).
- **Dependency audit** — CI fails on vulnerable dependencies: `pip-audit` for Python
  (`audit` job) and `pnpm audit --audit-level=high` for the web app (`web-ci.yml`).
- **Dependabot** — weekly update PRs for `pip`, `npm`, and `github-actions`
  (`.github/dependabot.yml`).

### Manual repo setting (one-time)
Enable GitHub-side protection under **Settings → Code security & analysis**:
- **Secret scanning** — on
- **Push protection** — on (blocks pushes containing detected secrets)

These complement the local gitleaks hook for contributors who haven't installed it.

## Supported versions
The `main` branch receives security fixes. Releases are tagged with SemVer.
