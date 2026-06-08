# Roadmap

Phased build: from the perimeter where entity-linkage is cleanest (State central) outward to
the hardest (social security). Each phase ships something useful on its own and de-risks the
next. Rationale in the feasibility & maintainability briefs and [ADRs](docs/adr/).

## Phase 0 — Validation spike  ·  *days*  ·  current

Prove the data join on real data before committing to the build.

- [ ] `spikes/phase0_siren_match` runs offline on fixtures (`make spike`)
- [ ] Discover the latest "jaune opérateurs" via the data.gouv.fr `/api/1` catalog (no slug)
- [ ] Validate one DECP extract against its Table Schema
- [ ] Snapshot a raw extract with provenance
- [ ] Measure the **SIREN match rate** across operators ↔ budget ↔ DECP (the go/no-go metric)

## Phase 1 — État-central MVP  ·  *4–8 weeks*

The graph that proves the concept.

- [ ] `Entity` + `Edge` model in Postgres (raw SQL migrations in `supabase/migrations`)
- [ ] Connectors: jaune opérateurs, PLF/LFI, execution (situation mensuelle)
- [ ] Graph: ministries → operators (tutelle), budget facts attached to entities
- [ ] Attributions: decrees (Légifrance/PISTE) + LOLF nomenclature
- [ ] Reads: PostgREST tables + the `graph_neighbors` RPC under RLS (no bespoke API server)
- [ ] Web: Sigma.js graph + entity sheet (budget · mission · tutelle)

## Phase 2 — Delegated services  ·  *+3–5 weeks*

First "public money → private operator" view.

- [ ] DECP connector (marchés + concessions) with schema validation
- [ ] `Contract` edges linking public buyers ↔ suppliers
- [ ] D3 Sankey of flows; supplier drill-down

## Phase 3 — Local authorities  ·  *+4–6 weeks*

- [ ] OFGL connector (balances comptables) + EPL (SEM/SPL) via SIRENE
- [ ] Second accounting universe → explicit anti-double-counting conventions + UI warnings

## Phase 4 — Social sphere  ·  *+4–6 weeks*

- [ ] Social accounts (DREES / Urssaf / LFSS), likely an aggregated module
- [ ] Whole-perimeter overview with methodology notes

## Cross-cutting (ongoing)

- [ ] Monitoring: reachability, freshness, schema conformity, volume deltas
- [ ] Entity crosswalk governance (quarterly review of unresolved links)
- [ ] Accessibility (RGAA) and i18n of the UI
