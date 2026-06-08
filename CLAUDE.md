# Contributor & AI-agent guide

Orientation for anyone — human contributor or AI coding agent — working in this repo. Read
this first, then [CONTRIBUTING.md](CONTRIBUTING.md) for the day-to-day workflow.

## What we're building

**Cartographie des Fonds Publics** — an interactive tool that maps how French public
institutions are linked, funded, mandated, and how public money flows to delegated
(public & private) operators. Built only on open data. Mission: help people understand how
public funds are used.

Full design: **[ARCHITECTURE.md](ARCHITECTURE.md)**. Plan: **[ROADMAP.md](ROADMAP.md)**.
Decisions: **[docs/adr/](docs/adr/)**. Hosting: **[DEPLOYMENT.md](DEPLOYMENT.md)**.

## Golden rules (non-negotiable)

1. **Never hardcode a dataset slug or URL.** All sources live in
   `data/registry/sources-registry.yaml`. To add/fix a source, edit the registry — not code.
2. **Discover, don't freeze.** Resolve datasets via the data.gouv.fr `/api/1` catalog
   (organisation + tag + millésime). The annual PLF re-slug must require zero code changes.
3. **Validate every extract** against its Table Schema; **fail loud** on drift.
4. **Snapshot raw extracts** (Parquet) with provenance before transform.
5. **SIREN is the canonical join key.** Unresolved links go to the reviewed crosswalk —
   never guess, never silently drop. Report the **match rate**.
6. **Curated in Postgres, heavy in Parquet.** Only the curated graph + aggregates go into
   Supabase. Raw DECP/SIRENE stay as Parquet artifacts. Load summaries, not dumps.
7. **Reads go through Supabase directly** — PostgREST + the `graph_neighbors` RPC, under
   **RLS public-read**. There is **no bespoke API server**. The `anon` key is public; the
   `service-role` key is server-only (ingestion / CI) and must never reach the browser.
8. **Methodology is explicit.** Money-flow aggregation documents its anti-double-counting
   convention in code and surfaces it in the UI.
9. **Conventional Commits, 1 feature = 1 PR.** Tests + lint + types must pass.
10. **No secrets, no raw snapshots in git.**

## Commands

```bash
make install     # uv sync + pnpm install
make spike       # Phase-0 SIREN-match spike (offline sample)
make supabase-up # start the local DEV Supabase stack in Docker (auto-applies migrations)
make db-migrate  # apply supabase/migrations/*.sql to $DATABASE_URL (prod apply path)
make ingest      # ingestion pipeline (reads data/registry, writes Supabase)
make refresh     # discover latest millésimes for all sources
make web         # run the frontend (reads Supabase)
make up / down   # optional local Redis cache (prod uses Supabase)
make lint format typecheck test   # quality gates (must pass before PR)
```

## Tech stack

Python 3.11+ (ingestion/core) in GitHub Actions. **Supabase** = database + API (Postgres +
PostgREST + RPC + RLS). **React + Vite + TypeScript + DSFR** on **Vercel**, using
`@supabase/supabase-js`; graph via Sigma.js/graphology, flows via D3. Redis optional cache.
uv (Python), pnpm (web). Ruff, mypy, pytest. Full table in ARCHITECTURE.md.

## Where things live

- `data/registry/` — the source registry (single source of truth).
- `packages/ingestion` — connectors (discover/extract/validate/snapshot/stage).
- `packages/core` — domain model + entity resolution (`normalize_siren`, crosswalk).
- `supabase/migrations` — schema, RLS, the `graph_neighbors` RPC. **This is the API.**
- `packages/web` — frontend; `src/lib/supabase.ts` is the read client.

## Definition of Done

- Code typed; `make lint format typecheck test` green.
- New behaviour covered by tests (connectors: contract tests against a fixture, no network).
- Source added/changed → only the registry edited; a schema ref set; a test exists.
- New curated table → next-numbered migration in `supabase/migrations` (see the conventions in
  `supabase/README.md`) with an RLS public-read policy; added to `tests/rls_checks.sql` and
  `make db-verify` passes.
- Docs/CHANGELOG updated when relevant. PR title is a Conventional Commit.

## How to add a new data source

1. Add an entry to `data/registry/sources-registry.yaml` (id, layer, platform, **discovery
   strategy**, schema ref, cadence, license, join keys, volatility).
2. Reuse or implement a `Connector` (`packages/ingestion/src/ingestion/connectors/`).
3. Point `schema` at the Table Schema when one exists (enables validation + drift detection).
4. Add a contract test with a small fixture — follow the offline harness + template in
   `packages/ingestion/tests/connectors/README.md`.
5. `make ingest`; verify snapshot + validation + the SIREN match impact; load curated rows to Supabase.

## Domain glossary

- **PLF / LFI** — projet / loi de finances (proposed / enacted State budget, annual).
- **LFSS / PLFSS** — social-security financing law (separate from the State budget).
- **LOLF** — budget nomenclature: *mission → programme → action → sous-action*.
- **AE / CP** — autorisations d'engagement (commitments) / crédits de paiement (cash).
- **Opérateur de l'État** — agency funded & overseen by a ministry; the "jaune opérateurs"
  lists ~430 with their **tutelle** (supervising ministry).
- **Jaune budgétaire** — PLF annexes (operators, subsidised associations…).
- **DECP** — données essentielles de la commande publique (contracts + concessions).
- **DSP / concession** — delegation of a public service to an operator (often private).
- **SEM / SPL / EPL** — local semi-public / public companies (delegated-service layer).
- **SIREN / SIRET** — 9-digit entity ID / 14-digit establishment ID (our join key).
- **OFGL** — observatory of local public finances. **APU** — full public-sector perimeter.
- **Cour des comptes / CRTC** — national / regional public audit bodies.

## Current phase

**Phase 0 → 1.** Prove the SIREN-join on real data (`spikes/phase0_siren_match`), then build
the **État-central MVP** (ministries → operators → budget → attributions). Do not attempt the
full perimeter at once — extend outward per ROADMAP.
