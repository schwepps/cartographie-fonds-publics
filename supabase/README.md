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

Dev and prod stay in parity because both paths run the **same** `migrations/*.sql` in lexical
order. Dev = local stack (see [config.toml](config.toml)); prod = the Supabase Pro project.

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

## Verify RLS

`make db-verify` runs [`tests/rls_checks.sql`](tests/rls_checks.sql): it asserts that `anon`
can SELECT every curated table and call `graph_neighbors`, but cannot INSERT/UPDATE/DELETE.
It expects a Supabase-like database (roles + grants present). Against the **local CLI stack**
it works directly (roles exist):

```bash
DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres make db-verify
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
