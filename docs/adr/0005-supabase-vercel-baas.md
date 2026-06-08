# 5. Supabase + Vercel + Redis (BaaS, no bespoke API server)

- Status: accepted
- Date: 2026-06-08
- Supersedes the "bespoke FastAPI server" part of [ADR-0002](0002-postgresql-service-backed.md).
  PostgreSQL + recursive-CTE graph traversal still holds — Supabase *is* PostgreSQL.

## Context
We already have **Supabase Pro**, Redis, and Vercel accounts and want a simple,
low-maintenance, cost-effective setup. An always-on API server is a tier we don't need for a
read-mostly public dataset.

## Decision
- **Database + API:** Supabase (managed PostgreSQL). Curated tables are read directly via
  PostgREST under Row Level Security (public SELECT); graph traversal is the
  `graph_neighbors` SQL function exposed as an RPC. No bespoke server.
- **Frontend:** React on **Vercel** (Hobby plan — free for non-commercial use), reading Supabase with the anon key.
- **Ingestion:** Python batch job in **GitHub Actions** (scheduled), writing via the
  service-role key / direct Postgres. Heavy staging stays in DuckDB/Parquet.
- **Cache/coordination:** **Redis** (optional) in front of expensive RPCs / ingestion locks.

## Consequences
- No container host to run or pay for. Supabase **Pro** ($25/mo) gives an 8 GB database,
  **no project pausing**, and daily backups — ample for the curated graph + aggregates.
- Keeping raw/heavy extracts as Parquet (not in Postgres) stays good practice for cost/perf,
  but is no longer forced by a 500 MB cap.
- Monthly refresh cron is sufficient (no keep-alive needed — Pro projects don't pause).
- If bespoke server logic is later required, use **Vercel Functions** (serverless).
