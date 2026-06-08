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

## Local development (dev environment)

**Dev is a full Supabase running locally in Docker** via the Supabase CLI — not the prod
project. This lets parallel Conductor worktrees develop safely with **no path to production
writes** (everything is `127.0.0.1`). Prerequisites: **Docker** and the
[Supabase CLI](https://supabase.com/docs/guides/cli).

```bash
make supabase-up     # `supabase start` — Postgres + PostgREST + Auth + Studio in Docker;
                     # auto-applies supabase/migrations/*.sql on a fresh DB
cp .env.example .env                     # root: ingestion env (local defaults, no secrets)
cd packages/web && cp .env.example .env  # web: VITE_SUPABASE_* (local defaults)
make web             # frontend reads the local stack at http://127.0.0.1:54321
make db-verify       # optional: assert RLS posture (DATABASE_URL must point at :54322)
make supabase-down   # stop the stack
```

Both `.env.example` files ship the **public local demo keys** (issuer `supabase-demo`,
localhost-only — not secrets; re-fetch any time with `supabase status -o env`). After adding a
migration, run `make supabase-reset` to re-apply.

> **Dev ↔ prod boundary.** Local dev uses only local demo keys and never touches prod. Do
> **not** `supabase link` / `supabase db push` the production project for routine dev — prod
> migrations go through `make db-migrate` against the prod `DATABASE_URL` (§1). Production
> secrets live only in GitHub Actions / Vercel, never in a local file. See SECURITY.md.

---

The sections below are the **production** deploy (the prod Supabase Pro project + Vercel + CI).

## 1. Supabase (database + API) — production

1. Create a project (you're on **Pro**: 8 GB DB, daily backups, **no auto-pause**).
2. Apply the schema with `DATABASE_URL` pointing at the **prod** project:
   ```bash
   make db-migrate     # runs supabase/migrations/*.sql against $DATABASE_URL (psql, fail-loud)
   ```
   This creates the curated tables, **RLS public-read** policies, and the `graph_neighbors`
   RPC — the same migrations the local dev stack applies, so dev and prod stay in parity.
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

- [ ] Prod Supabase project created; `make db-migrate` applied against the prod `DATABASE_URL`
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
