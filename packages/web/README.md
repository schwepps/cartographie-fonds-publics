# web

React + Vite + TypeScript frontend. Graph via **Sigma.js/graphology**, flows via **D3** (Sankey),
UI via the French State Design System (**@gouvfr/dsfr**). It reads **Supabase directly** —
PostgREST for tables and the `graph_neighbors` RPC for graph traversal, under Row Level Security
(public read). There is no bespoke API server.

## Quickstart

```bash
pnpm install
cp .env.example .env        # then set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY
pnpm dev                    # http://localhost:5173
```

Point the two `VITE_SUPABASE_*` variables at a Supabase project that has the migrations in
[`supabase/migrations`](../../supabase/migrations) applied (see the repo
[DEPLOYMENT.md](../../DEPLOYMENT.md)). The `anon` key is safe to expose; never put the
`service-role` key in the frontend.

## Scripts

```bash
pnpm dev          # dev server
pnpm build        # type-check (tsc -b) + production build
pnpm typecheck    # tsc --noEmit
pnpm lint         # eslint
pnpm format       # prettier --write
```
