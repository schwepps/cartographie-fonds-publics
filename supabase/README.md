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
make db-migrate          # psql "$DATABASE_URL" -f migrations/*.sql
```

## Size discipline
Pro gives an 8 GB database — ample for the curated graph + aggregates. Still load **summaries,
not source dumps**: raw DECP/SIRENE extracts stay as Parquet artifacts from ingestion.
