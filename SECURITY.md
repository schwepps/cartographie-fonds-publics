# Security Policy

## Reporting a vulnerability
Please **do not** open a public issue for security problems.
Report privately via GitHub: open the repository's **Security** tab → **Report a vulnerability**
(GitHub [private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)).
Include details and steps to reproduce. We aim to acknowledge within 5 business days.

## Scope & data
- This project only ingests **public open data** (Licence Ouverte / Etalab 2.0).
- No **production** secrets are committed (the only committed keys are the public local-dev
  demo JWTs — see *Secrets & environments* below). Credentials live in `.env` (gitignored) or
  CI secrets.
- Raw data snapshots are never committed (see `.gitignore`).

## Secrets & environments

There are two environments. **Dev** is a full Supabase running locally in Docker (the Supabase
CLI stack, `make supabase-up`); **prod** is the Supabase Pro project. They never share
credentials, and dev has **no path to production writes** — every dev value points at
`127.0.0.1`.

Which value goes where:

| Variable | Dev (local) | Prod | Lives in | Sensitive? |
|---|---|---|---|---|
| `VITE_SUPABASE_URL` | `http://127.0.0.1:54421` | prod Project URL | `packages/web/.env` / **Vercel env** | no |
| `VITE_SUPABASE_ANON_KEY` | local demo JWT | prod anon key | `packages/web/.env` / **Vercel env** | no — RLS-protected, ships to browser |
| `SUPABASE_URL` | `http://127.0.0.1:54421` | prod Project URL | root `.env` | no |
| `SUPABASE_SERVICE_ROLE_KEY` | local demo JWT | prod service-role key | root `.env` (local) / **GitHub Actions secret** | **yes (prod)** — server/CI only, **never** the browser |
| `DATABASE_URL` | `postgresql://postgres:postgres@127.0.0.1:54422/postgres` | prod direct Postgres URI | root `.env` (local) / **GitHub Actions secret** | **yes (prod)** |

Rules:

- **Service-role key is server-only.** It is used solely by ingestion (GitHub Actions) and
  local scripts — it must never reach the frontend bundle or any `VITE_*` variable. The web app
  uses only the **anon** key under RLS public-read.
- **Production secrets live only in GitHub Actions secrets** (`DATABASE_URL`,
  `SUPABASE_SERVICE_ROLE_KEY`) and **Vercel env** (`VITE_SUPABASE_*`) — never in a committed
  file or a local `.env`.
- **Local demo keys are not secrets.** The `anon`/`service_role` JWTs the CLI mints (issuer
  `supabase-demo`) are public, identical on every machine, and valid only against the local
  stack. They ship in the `.env.example` files; `.gitleaks.toml` allowlists *only* those two
  exact demo tokens, so any other key — including a real one — is still blocked by secret
  scanning.
- **Never `supabase link` / `supabase db push` the prod project for routine dev.** Prod
  migrations go through `make db-migrate` against the prod `DATABASE_URL`.
- If a prod key is ever exposed, **rotate it in the Supabase dashboard** and update the GitHub
  Actions secret / Vercel env.

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
