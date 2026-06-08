# Deployment

Simple, low-maintenance, cost-effective — using the accounts you already have:
**Supabase (Pro)** for the database + API, **Vercel** for the frontend, **GitHub Actions**
for ingestion, and **Redis** (optional) for caching. No container host, no always-on server.

## Topology

```
GitHub Actions (cron)  --writes-->  Supabase Postgres  <--reads (anon+RLS)--  Vercel (React)
   ingestion job                    (DB + PostgREST + RPC)                     static frontend
        |                                   ^
   Parquet artifacts                        | optional cache
   (Supabase Storage / release)           Redis
```

The frontend talks to Supabase **directly** (PostgREST for tables, the `graph_neighbors` RPC
for traversal), protected by Row Level Security (public read). See
[ADR-0005](docs/adr/0005-supabase-vercel-baas.md).

## 1. Supabase (database + API)

1. Create a project (you're on **Pro**: 8 GB DB, daily backups, **no auto-pause**).
2. Apply the schema:
   ```bash
   # Option A — Supabase CLI (local parity):
   supabase link --project-ref YOUR_REF && supabase db push
   # Option B — psql:
   make db-migrate     # runs supabase/migrations/*.sql against $DATABASE_URL
   ```
   This creates the curated tables, **RLS public-read** policies, and the `graph_neighbors`
   RPC.
3. Grab the **Project URL** and **anon key** (frontend) and **service-role key** (ingestion).

> Keep only the **curated graph + aggregates** here. Raw DECP/SIRENE extracts stay as Parquet
> artifacts (Supabase Storage 100 GB on Pro, or a GitHub release). Pro's 8 GB is ample for
> curated data; load summaries, not dumps.

## 2. Vercel (frontend)

1. **New Project → import the GitHub repo.** Set **Root Directory = `packages/web`** (this is a
   monorepo). Vercel auto-detects Vite; `packages/web/vercel.json` provides the build command,
   output dir (`dist`), and SPA rewrite.
2. Set env vars: `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`.
3. Every push to `main` auto-deploys; PRs get preview URLs. Free tier ≈ 100 GB bandwidth/month.

> ⚠️ **Hobby (free) is non-commercial / personal use only.** A free public-interest tool is
> generally fine, but if the project ever generates revenue (donations with perks, ads, paid
> features), Vercel's terms require **Pro ($20/mo)**. If you'd rather avoid that line entirely,
> **Netlify's free tier permits commercial use** — the frontend is plain Vite, so swapping back
> is just a `vercel.json` ↔ `netlify.toml` change.

## 3. Ingestion (GitHub Actions)

`.github/workflows/data-refresh.yml` runs monthly (and on demand). Add repo **secrets**:
`DATABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`. The job discovers latest millésimes, validates,
snapshots to Parquet, and loads curated data into Supabase. Because Pro doesn't pause, a
monthly cadence is enough — **no keep-alive job needed**.

## 4. Redis (optional)

Use your Redis to cache expensive RPC results (e.g. large neighbourhoods / Sankey aggregates)
and as an ingestion lock. Not required for the MVP — add it when a query is measurably slow.

## First-deploy checklist

- [ ] Supabase project created; `make db-migrate` (or `supabase db push`) applied
- [ ] Verify RLS: anon can `select` curated tables and call `graph_neighbors`; cannot write
- [ ] Vercel project connected; **Root Directory = `packages/web`**; `VITE_SUPABASE_*` env set; first deploy green
- [ ] GitHub secrets `DATABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` set; run `data-refresh` once
- [ ] Confirm the spend cap is **on** in Supabase (default) to avoid surprise overage
- [ ] Custom domain + HTTPS on Vercel (automatic)
- [ ] (Optional) wire Redis `REDIS_URL`; add Sentry `SENTRY_DSN`

## Cost

≈ **$25/month** (Supabase Pro). Vercel Hobby is free (non-commercial; Pro is $20/mo if you
later monetise), GitHub Actions is free for public repos, Redis on your existing account.
Scale by turning off Supabase's spend cap only when you choose to.

## Notes on sovereignty

Supabase and Vercel are US-headquartered. For French public *open* data this is generally fine
(nothing confidential). If strict data residency ever becomes a requirement, the containerised
parts (ingestion, and a future API if ever added) can move to an EU host (Scaleway / Clever
Cloud) without touching application code — that's why ingestion is plain Python and the data
layer is standard Postgres.

## References

- [Supabase pricing](https://supabase.com/pricing) · [Vercel pricing](https://vercel.com/pricing) ·
  [Vercel Hobby plan](https://vercel.com/docs/plans/hobby)
- [Supabase RLS](https://supabase.com/docs/guides/database/postgres/row-level-security) ·
  [PostgREST functions/RPC](https://supabase.com/docs/guides/database/functions)
- [Licence Ouverte / Etalab 2.0](https://www.etalab.gouv.fr/licence-ouverte-open-licence/)
