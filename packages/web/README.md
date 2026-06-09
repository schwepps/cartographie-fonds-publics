# web

React + Vite + TypeScript frontend. Routing via **react-router**; the institutional graph is a
custom **2D-canvas** force-directed layout (`src/features/graph/GraphCanvas.tsx`) and money flows
render as a hand-rolled **SVG Sankey** (`src/lib/ui/Sankey.tsx`). The UI follows the French State
Design System (DSFR): a **self-contained design layer** — design tokens, Marianne fonts and base
components — ported from the delivered design export (see `src/styles/` and `src/lib/ui/`). It
reads **Supabase directly** — PostgREST for tables and the `graph_neighbors` RPC, under Row Level
Security (public read). There is no bespoke API server.

## App shell & feature folders

The app shell (`src/App.tsx` + `src/app/Layout.tsx`) is **frozen**. Every feature is a
self-contained folder under `src/features/<name>/`, registered with one line in
`src/app/routes.tsx` — so feature lanes progress in parallel. See
[`src/features/README.md`](src/features/README.md) for the convention.

> The design system — tokens, the DSFR-faithful base/components, app chrome and the Marianne
> fonts — lives under `src/styles/` and is imported once in `src/main.tsx`. The base component
> library is `src/lib/ui/`. The original design export has been fully ported into these and
> removed; its prototype lives on in git history.

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
