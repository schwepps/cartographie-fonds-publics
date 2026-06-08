# Contributing

Thanks for helping make public spending understandable. This guide gets you productive fast.

By participating you agree to our [Code of Conduct](CODE_OF_CONDUCT.md).

## Development setup

Prerequisites: **Python 3.11+** with [uv](https://github.com/astral-sh/uv), **Node 20+** with
[pnpm](https://pnpm.io/), **Docker**, and the [Supabase CLI](https://supabase.com/docs/guides/cli)
(for the local dev database).

```bash
git clone https://github.com/schwepps/cartographie-fonds-publics.git
cd cartographie-fonds-publics
cp .env.example .env          # ships working local-dev defaults (no secrets to fill in)
make install
make spike            # sanity check: runs offline, prints a SIREN match rate
make supabase-up      # start the local dev Supabase stack (Docker) + apply migrations
make up               # optional: local Redis cache (prod uses Supabase)
```

The local dev database is a full Supabase running in Docker — **isolated from production**.
See [DEPLOYMENT.md → Local development](DEPLOYMENT.md) for the full loop and the dev↔prod
secrets boundary ([SECURITY.md](SECURITY.md)).

## Workflow

- **One feature/fix per pull request.** Small PRs get reviewed faster.
- **Conventional Commits** for commit messages and PR titles:
  `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:` (e.g. `feat(ingestion): add OFGL connector`).
  This is **enforced** by a `commit-msg` hook (commitlint) — non-conforming messages are rejected.
- Branch off `main`; open a PR; fill in the template checklist.
- All checks must pass: `make lint format typecheck test`.

### Branch protection (`main`)

`main` is protected so no one — human or agent — can merge a PR with red CI. The required
status checks are **`python`**, **`web`**, and **`database`** (the job names in
[`ci.yml`](.github/workflows/ci.yml) and [`web-ci.yml`](.github/workflows/web-ci.yml)); names
must match the jobs exactly. The `secrets` (gitleaks) and `audit` (pip-audit / pnpm audit) jobs
stay advisory — they can fail on upstream advisories unrelated to a given PR.

> The `web` check is a lightweight gate job that **always runs** and reports success when
> `packages/web/**` is untouched, so non-web PRs never hang waiting for it. The actual web
> gates run in the `build` job only when web files change.

Enabling protection is a one-time admin action. With the GitHub CLI (`gh auth login` as a repo
admin first):

```bash
gh api -X PUT repos/schwepps/cartographie-fonds-publics/branches/main/protection \
  --input - <<'JSON'
{
  "required_status_checks": {
    "strict": true,
    "checks": [
      { "context": "python" },
      { "context": "web" },
      { "context": "database" }
    ]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": null,
  "restrictions": null
}
JSON
```

Trade-offs to set deliberately:

- `strict: true` — a PR must be up to date with `main` before merging (re-runs CI when the base
  moves). Set `false` if forced re-runs become noisy with many parallel PRs.
- `enforce_admins: true` — admins are bound by CI too. This is the point; flip to `false` only
  if you need an emergency-merge escape hatch.
- `required_pull_request_reviews: null` — no review required, so a solo maintainer can self-merge
  green PRs. Add a review requirement here once there are other reviewers.

Equivalent via the UI: **Settings → Branches → Add branch ruleset/rule** for `main` →
**Require status checks to pass before merging** → add `python`, `web`, `database` → also tick
**Require branches to be up to date** and **Do not allow bypassing the above settings** to match
the CLI body above.

### Git hooks

`make install` runs `pre-commit install`, which wires both the `pre-commit` and `commit-msg`
stages automatically — no separate step. On every commit the hooks:

- **commit message** → commitlint enforces Conventional Commits;
- **staged Python** → ruff lint (`--fix`) + ruff format (staged files only);
- **web** → when any `packages/web` file is staged, ESLint + Prettier lint the **whole**
  `packages/web` package (not just the staged files), matching web CI;
- **all staged changes** (any file type) → gitleaks secret scan (blocks committing secrets).

Hooks fire based on the staged file set; the ruff and gitleaks checks operate on the staged
changes themselves, while the web check runs across the package. If you ever need to bootstrap
hooks manually, run `uv run pre-commit install`.

## Adding or fixing a data source

This is the most common contribution. **Edit the registry, not the code.**

1. Add/update the entry in [`data/registry/sources-registry.yaml`](data/registry/sources-registry.yaml).
2. Set a `discovery.strategy` (organisation + tag + millésime) — **no frozen slugs**.
3. Point `schema` at the Table Schema if one exists (enables validation).
4. Reuse or add a `Connector` and a contract test with a small fixture.

See [CLAUDE.md](CLAUDE.md) for the golden rules and the full step list.

## Tests

`make test` runs pytest across packages and the spike. New behaviour needs a test;
connectors need a contract test against a fixture (don't hit the network in unit tests).
Follow the offline harness and template in
[`packages/ingestion/tests/connectors/README.md`](packages/ingestion/tests/connectors/README.md).

Touching the schema? Follow the migration-numbering convention in
[`supabase/README.md`](supabase/README.md) (each ticket claims the next `NNNN_` file) and run
`make db-verify` to confirm the public-read RLS posture still holds.

## Reporting issues

Use the templates: **bug**, **feature**, or **data source** (when a source's URL, schema, or
slug changed). For security, see [SECURITY.md](SECURITY.md) — do not open a public issue.

## Licensing of contributions

Contributions are licensed under the project's [AGPL-3.0-or-later](LICENSE).
