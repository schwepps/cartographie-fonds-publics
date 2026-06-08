# supabase

Database + API via [Supabase](https://supabase.com/) (managed PostgreSQL). **No bespoke API
server**: the frontend reads curated tables directly through PostgREST (Row Level Security =
public read), and graph traversal is the `graph_neighbors` SQL function called as an RPC.
See [ADR-0005](../docs/adr/0005-supabase-vercel-baas.md).

## Apply migrations

```bash
# Option A — Supabase CLI (local parity):
supabase link --project-ref YOUR_REF && supabase db push
# Option B — psql / make:
make db-migrate          # applies every migrations/*.sql in order, fails loud on drift
```

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
  roles plus their baseline table grants already exist in production — migrations must **not**
  create them. (For a bare Postgres, `tests/supabase_roles.sql` recreates that baseline; see
  below.)
- **New curated table → public-read RLS in the same migration**, and add the table to the loop
  list in [`tests/rls_checks.sql`](tests/rls_checks.sql) so the RLS check covers it.

## Verify RLS

`make db-verify` runs [`tests/rls_checks.sql`](tests/rls_checks.sql): it asserts that `anon`
can SELECT every curated table and call `graph_neighbors`, but cannot INSERT/UPDATE/DELETE.
It expects a Supabase-like database (roles + grants present), so against a **bare** Postgres
(`make up`, or CI) apply the compatibility shim first:

```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f supabase/tests/supabase_roles.sql  # bare Postgres only
make db-migrate
make db-verify
```

CI runs exactly this against a fresh `postgres:16` on every PR.

## Size discipline
Pro gives an 8 GB database — ample for the curated graph + aggregates. Still load **summaries,
not source dumps**: raw DECP/SIRENE extracts stay as Parquet artifacts from ingestion.
