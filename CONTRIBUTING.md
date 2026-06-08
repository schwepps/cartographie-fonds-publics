# Contributing

Thanks for helping make public spending understandable. This guide gets you productive fast.

By participating you agree to our [Code of Conduct](CODE_OF_CONDUCT.md).

## Development setup

Prerequisites: **Python 3.11+** with [uv](https://github.com/astral-sh/uv), **Node 20+** with
[pnpm](https://pnpm.io/), and **Docker** (optional — local Postgres/Redis).

```bash
git clone https://github.com/schwepps/cartographie-fonds-publics.git
cd cartographie-fonds-publics
cp .env.example .env          # then set VITE_SUPABASE_* + DATABASE_URL (see DEPLOYMENT.md)
make install
make spike        # sanity check: runs offline, prints a SIREN match rate
make up           # optional: local Postgres + Redis (prod uses Supabase)
```

## Workflow

- **One feature/fix per pull request.** Small PRs get reviewed faster.
- **Conventional Commits** for commit messages and PR titles:
  `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:` (e.g. `feat(ingestion): add OFGL connector`).
- Branch off `main`; open a PR; fill in the template checklist.
- All checks must pass: `make lint format typecheck test`. Install the hooks once with
  `uv run pre-commit install`.

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
