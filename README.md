# Cartographie des Fonds Publics

> Understand how French public money is used — who is linked to whom, funded how, for which
> mission, and which (public and private) operators it ultimately flows to.

[![CI](https://github.com/schwepps/cartographie-fonds-publics/actions/workflows/ci.yml/badge.svg)](https://github.com/schwepps/cartographie-fonds-publics/actions)
[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](LICENSE)

An interactive, open-source map of French public institutions: their **links**
(tutelle, participations), their **funding** (budget & flows), their **mandates**
(attributions), and the **delegated services** they contract out — built entirely on
**open data** (Licence Ouverte / Etalab 2.0).

> **Status:** feature-complete locally, pre-launch. Phases 1–4 are delivered — the full
> four-layer perimeter (État central · delegated services · local authorities · social sphere)
> runs end-to-end. Remaining: ministerial attributions, a Cour des comptes oversight layer, and
> deployment. See [ROADMAP.md](ROADMAP.md).

## Why

Existing tools show the State budget in isolation. None combine the *institutional graph*
with funding flows, legal mandates, and delegated (private) services across the public
sector. That graph is the gap this project fills.

## How it works

Registry-driven ingestion (discover → validate → snapshot → stage) runs as a scheduled
**GitHub Actions** job and loads a curated graph into **Supabase** (managed PostgreSQL). The
**React/DSFR frontend on Vercel reads Supabase directly** — PostgREST for tables, a SQL
`graph_neighbors` RPC for traversal, with Row Level Security for public read. **No bespoke API
server.** Sources drift, so **nothing is hardcoded**: all sources live in
[`data/registry/sources-registry.yaml`](data/registry/sources-registry.yaml) and are resolved
by discovery. Full design in **[ARCHITECTURE.md](ARCHITECTURE.md)**.

## Quickstart

```bash
make install                         # Python (uv) + web (pnpm) deps
make spike                           # Phase-0 SIREN-match proof (offline, no network)
make supabase-up                     # local DEV Supabase in Docker (applies migrations on first start)
cd packages/web && cp .env.example .env && pnpm dev   # frontend reads the local stack
```

Frontend dev server runs on `:5173`; the "API" is the local Supabase stack (PostgREST + RPC) at
`127.0.0.1:54421` — a full Supabase in Docker, isolated from prod. Setup + the dev↔prod
boundary: [DEPLOYMENT.md → Local development](DEPLOYMENT.md).

## Stack

Python ingestion (GitHub Actions) · **Supabase** (Postgres + PostgREST + RPC + RLS) ·
React + Vite + DSFR + Sigma.js + D3 on **Vercel** · Redis (optional cache). Hosting is
~$25/mo (Supabase Pro); see [DEPLOYMENT.md](DEPLOYMENT.md).

## Data & licensing

- **Data:** public, [Licence Ouverte / Etalab 2.0](https://www.etalab.gouv.fr/licence-ouverte-open-licence/).
  Sources are listed in the registry; attribution is preserved.
- **Code:** [AGPL-3.0-or-later](LICENSE) ([ADR-0004](docs/adr/0004-license-agpl.md)).

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
To report a source that changed, use the **data source** issue template.

## Documentation

[Architecture](ARCHITECTURE.md) · [Roadmap](ROADMAP.md) · [Deployment](DEPLOYMENT.md) ·
[Decisions (ADR)](docs/adr/) · [Contributor & AI-agent guide (CLAUDE.md)](CLAUDE.md)
