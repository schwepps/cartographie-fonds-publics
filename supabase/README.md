# supabase

Database + API via [Supabase](https://supabase.com/) (managed PostgreSQL). **No bespoke API
server**: the frontend reads curated tables directly through PostgREST (Row Level Security =
public read), and graph traversal is the `graph_neighbors` SQL function called as an RPC.
See [ADR-0005](../docs/adr/0005-supabase-vercel-baas.md).

## Apply migrations

```bash
# Local dev (Supabase CLI stack): `make supabase-up` (supabase start) auto-applies every
# migrations/*.sql on a fresh DB; after adding a new one, re-apply with:
make supabase-reset      # supabase db reset — drops local DB and re-applies all migrations
# Production: psql over the direct connection (same files, same order, fails loud on drift):
make db-migrate          # applies every migrations/*.sql against $DATABASE_URL
```

Dev and prod stay in **schema** parity because both paths run the **same** `migrations/*.sql`
in lexical order. Dev = local stack (see [config.toml](config.toml)); prod = the Supabase Pro
project. (Parity is about the migrations, not the engine version: set `[db] major_version` in
`config.toml` to match prod; CI runs the RLS shim check against a bare `postgres:16`.)

## Migration conventions

- **Filename:** `NNNN_short_description.sql` — zero-padded 4-digit prefix, `snake_case`
  description (e.g. `0003_decp_contracts.sql`). Migrations apply in **lexical order**, which
  the zero-padding makes equal to numeric order. `make db-migrate` globs `migrations/*.sql`,
  so a new file needs **no** Makefile change.
- **One migration = one logical change.** Each connector/feature ticket **claims the next free
  number in its PR**. If two PRs grab the same number, the second to merge rebases and renumbers
  — never reuse or reorder an existing number.
- **Append-only & idempotent.** Use `create table if not exists`, `create index if not exists`,
  `create or replace function`. **Never edit a migration already applied to a shared database** —
  add a new one. `ON_ERROR_STOP=1` means any failure aborts the run loudly.
- **Roles & grants are Supabase-provided.** The `anon`, `authenticated`, and `service_role`
  roles plus their baseline table grants already exist in production **and in the local CLI
  stack** — migrations must **not** create them. (Only a *bare* Postgres lacks them; CI uses
  `tests/supabase_roles.sql` to recreate that baseline — see below.)
- **New curated table → public-read RLS in the same migration**, and add the table to the loop
  list in [`tests/rls_checks.sql`](tests/rls_checks.sql) so the RLS check covers it.

## Seed (curated starter data)

[`seed.sql`](seed.sql) is a tiny, real, licence-attributed **État-central** slice (a few
ministries + operators + tutelle edges + PLF 2025 MIRES budget facts + real DECP contracts) so a
fresh dev DB — and Vercel previews — render a populated graph + entity sheet **before** the full
ingestion load (FSC-35) exists. It lets the web features (entity sheet, graph explorer, Sankey)
develop entirely against committed data.

```bash
# Local: auto-loaded on a fresh DB (config.toml `[db.seed]`) after migrations apply.
make supabase-reset      # supabase db reset — re-applies migrations, then loads seed.sql
# Any DB (preview / a running stack): regenerate + load over the direct connection.
make seed                # python -m ingestion.cli seed-emit, then psql -f seed.sql
```

- **Generated, not hand-edited.** `seed.sql` is rendered from `packages/ingestion`'s
  `ingestion.seed` builder, which constructs the frozen domain models (validation is free) and
  resolves every SIREN from `data/crosswalk/*.yaml` (never hardcoded). Edit the builder, then
  `make seed`; a golden test (`packages/ingestion/tests/test_seed.py`) fails loud if the committed
  SQL drifts from the builder.
- **Dev/preview only.** `seed.sql` **truncates** the curated tables before inserting, so it is
  idempotent for dev but must **never** run against the curated production database. `make seed`
  enforces this: it **refuses a non-local `DATABASE_URL`** unless `SEED_ALLOW_NONLOCAL=1` is set
  (the explicit opt-in for seeding a preview DB). The local auto-load on `supabase db reset` is
  unaffected.

## Verify RLS

`make db-verify` runs [`tests/rls_checks.sql`](tests/rls_checks.sql): it asserts that `anon`
can SELECT every curated table and call `graph_neighbors`, but cannot INSERT/UPDATE/DELETE.
It expects a Supabase-like database (roles + grants present). Against the **local CLI stack**
it works directly (roles exist):

```bash
DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:54422/postgres make db-verify
```

The `tests/supabase_roles.sql` compatibility shim is **CI-only**: CI runs against a fresh,
**bare** `postgres:16` (no Supabase roles), so it applies the shim first:

```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f supabase/tests/supabase_roles.sql  # bare Postgres only
make db-migrate
make db-verify
```

## Size discipline
Pro gives an 8 GB database — ample for the curated graph + aggregates. Still load **summaries,
not source dumps**: raw DECP/SIRENE extracts stay as Parquet artifacts from ingestion.
