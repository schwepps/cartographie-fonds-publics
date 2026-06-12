# Roadmap

Phased build: from the perimeter where entity-linkage is cleanest (State central) outward to
the hardest (social security). Each phase ships something useful on its own and de-risks the
next. Rationale in the feasibility & maintainability briefs and [ADRs](docs/adr/).

> **Status:** Phases 0–4 are **delivered locally** — the product is feature-complete end-to-end
> (ingest → resolve → load → read) on the full four-layer perimeter with anti-double-counting
> proven. Remaining before a public launch: ministerial **attributions** ([FSC-27]), a **Cour des
> comptes oversight** layer, and **deployment**. See "Remaining before launch" below.

## Phase 0 — Validation spike  ·  *delivered*

Prove the data join on real data before committing to the build.

- [x] `spikes/phase0_siren_match` runs offline on fixtures (`make spike`)
- [x] Discover the latest "jaune opérateurs" via the data.gouv.fr `/api/1` catalog (no slug)
- [x] Validate one DECP extract against its Table Schema
- [x] Snapshot a raw extract with provenance
- [x] Measure the **SIREN match rate** across operators ↔ budget ↔ DECP — **CONDITIONAL GO**
      ([docs/phase0-siren-match-results.md](docs/phase0-siren-match-results.md))

## Phase 1 — État-central MVP  ·  *delivered (attributions deferred)*

The graph that proves the concept.

- [x] `Entity` + `Edge` model in Postgres (raw SQL migrations in `supabase/migrations`)
- [x] Connectors: jaune opérateurs, PLF/LFI, execution (situation mensuelle)
- [x] Graph: ministries → operators (tutelle), budget facts attached to entities
- [ ] Attributions: decrees (Légifrance/PISTE) + LOLF nomenclature — **deferred** ([FSC-27])
- [x] Reads: PostgREST tables + the `graph_neighbors` RPC under RLS (no bespoke API server)
- [x] Web: institutional graph (custom 2D-canvas force layout, superseding Sigma v1) + entity
      sheet (budget · mission · tutelle)

## Phase 2 — Delegated services  ·  *delivered*

First "public money → private operator" view.

- [x] DECP connector (marchés + concessions) with schema validation
- [x] `Contract` edges linking public buyers ↔ suppliers
- [x] D3 Sankey of flows; supplier drill-down

## Phase 3 — Local authorities  ·  *delivered*

- [x] OFGL connector (balances comptables) + EPL (SEM/SPL) via SIRENE
- [x] Second accounting universe → explicit anti-double-counting conventions + UI warnings
      ([ADR-0007](docs/adr/0007-anti-double-counting-state-local.md))

## Phase 4 — Social sphere  ·  *delivered*

- [x] Social accounts (DREES / Urssaf / LFSS), aggregated module
- [x] Whole-perimeter overview with methodology notes; anti-double-counting **proven** on the real
      merged four-layer dataset

## Remaining before launch

- [ ] **Attributions** — ministerial decrees (Légifrance/PISTE) + LOLF nomenclature ([FSC-27])
- [ ] **Cour des comptes / CRTC oversight** layer (audit findings linked to entities)
- [ ] **Deployment** — production Supabase + Vercel per [DEPLOYMENT.md](DEPLOYMENT.md)

## Cross-cutting (ongoing)

- [x] Accessibility (RGAA AA pass on graph + Sankey, [docs/rgaa-conformance.md](docs/rgaa-conformance.md))
      and i18n of the UI
- [ ] Monitoring: reachability, freshness, schema conformity, volume deltas (scheduled-run alert in place)
- [ ] Entity crosswalk governance (quarterly review of unresolved links)

[FSC-27]: https://linear.app/fscconsulting/issue/FSC-27
