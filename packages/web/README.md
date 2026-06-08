# web

React + Vite + TypeScript frontend. Routing via **react-router**, graph via
**Sigma.js/graphology**, flows via **D3** (Sankey), UI via the French State Design System
(**@codegouvfr/react-dsfr**, the typed React layer over `@gouvfr/dsfr`). It reads **Supabase
directly** — PostgREST for tables and the `graph_neighbors` RPC for graph traversal, under Row
Level Security (public read). There is no bespoke API server.

## App shell & feature folders

The app shell (`src/App.tsx` + `src/app/Layout.tsx`) is **frozen**. Every feature is a
self-contained folder under `src/features/<name>/`, registered with one line in
`src/app/routes.tsx` — so feature lanes progress in parallel. See
[`src/features/README.md`](src/features/README.md) for the convention.

> DSFR assets are copied into `public/dsfr/` (gitignored) by `copy-dsfr-to-public`, which runs
> automatically on `postinstall`, `dev`, and `build`.

## Quickstart

```bash
pnpm install
cp .env.example .env        # ships local-dev defaults (local Supabase URL + demo anon key)
pnpm dev                    # http://localhost:5173
```

`.env.example` targets the **local dev** Supabase stack (`make supabase-up` from the repo root;
see [DEPLOYMENT.md → Local development](../../DEPLOYMENT.md)). For production, set
`VITE_SUPABASE_URL` + `VITE_SUPABASE_ANON_KEY` in the **Vercel** project env, pointing at the
prod project. The `anon` key is safe to expose; never put the `service-role` key in the
frontend.

## Scripts

```bash
pnpm dev          # dev server
pnpm build        # type-check (tsc -b) + production build
pnpm typecheck    # tsc --noEmit
pnpm lint         # eslint
pnpm format       # prettier --write
```
