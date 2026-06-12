# Changelog

All notable changes to this project are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/), versioning: [SemVer](https://semver.org/).
Commits follow [Conventional Commits](https://www.conventionalcommits.org/).

## [Unreleased]
### Added
- RGAA accessibility pass on the graph + Sankey (FSC-59): automated `vitest-axe` `toHaveNoViolations`
  assertions now cover the Graphe (page chrome **and** the table fallback), Recherche and Flux/Sankey
  screens too (joining Accueil, Fiche, Sources, Périmètre and the shell), so the key screens gate on
  axe in CI. The audit caught and fixed a real **heading-order** non-conformity (RGAA 9.1) — Graphe
  and Recherche jumped `<h1>` → `<h4>` for the filter/facet/legend titles; these are now `<h2>` with
  the small weight kept by class/selector. A manual keyboard + token-contrast audit (all body/UI text
  ≥ AA; the colour-blind-safe Okabe–Ito level fills are redundant graphical encoding, shape + outline
  + table, documented as accepted) and the keyboard contract for the graph + Sankey fallbacks are
  recorded in `docs/rgaa-conformance.md`.
- Performance pass on the graph + Sankey for the full dataset (FSC-60): a committed micro-benchmark
  (`pnpm bench`, `features/graph/perf.bench.ts`) over a synthetic graph an order of magnitude past
  the demo seed proves every pure hot path (`buildGraphModel`, `computeVisible`, `computeExpandable`,
  `buildFlowLinks`, `computeSankey`) stays **sub-millisecond at ~3 000 nodes**. The worst per-frame
  offender is fixed: the canvas no longer recomputes the expand affordance with an O(edges) scan per
  node (O(visibleNodes × edges) every frame) — `computeVisible`/`computeExpandable` are extracted as
  pure functions over a prebuilt filtered adjacency, the visible node/edge subsets are precomputed
  once per change (so `step()`/`draw()` stop re-filtering the whole model each frame), and the
  reduced-motion fast-settle is bounded by node count instead of a fixed 40× quadratic blast.
  Budgets, before/after and the evidence-based **defer-FSC-40 (Redis)** decision — the UI calls no
  heavy RPC, only plain PostgREST selects — are in `docs/perf-graph-sankey.md`.
- Docs refreshed to "feature-complete locally, pre-launch" (FSC-61): `ROADMAP.md` marks Phases 0–4
  delivered (attributions deferred) and lists what remains (attributions FSC-27, Cour des comptes
  oversight, deployment); `CLAUDE.md` "Current phase" and the `README.md` status line are updated to
  match the true state of the build.
- Anti-double-counting reconciliation proof on combined data (FSC-58): the methodology (ADR-0007) is
  now **verified**, not just documented. `core.methodology.perimeter_totals` is the canonical
  per-universe breakdown (the keys partition the facts, so the values never double-count across
  universes); tests prove the convention on the **real merged 4-layer dataset** — a pure
  `core` test, an offline whole-perimeter bundle test (`build_bundle(ALL_SOURCE_IDS)`, no DB), and
  DB reconciliation assertions on the actually-loaded graph in the FSC-57 pipeline test (per-universe
  CP sums partition the grand total exactly, spanning >1 universe, breakdown logged). State↔local
  transfers stay in `edges`/`contracts`, never folding into a budget universe total; the
  `perimetre` view is asserted to never render a consolidated cross-universe figure.
- Parallel-safe local Supabase ports (FSC-58): the CLI stack moved off the default `543xx` ports
  to a dedicated `544xx` block (API 54421, DB 54422, shadow 54420, Studio 54423) in
  `supabase/config.toml`, with all `.env.example` + docs references updated, so it runs alongside
  other local Supabase stacks on the same machine without a host-port clash (`project_id` already
  isolates the containers + volumes). Re-`cp .env.example .env` (root + `packages/web`) to pick up
  the new ports.
- Anti-double-counting methodology + UI disclaimers (FSC-42): a documented convention (ADR-0007) that
  the State (LOLF), local (M57/M14) and social accounting universes are **never silently summed**. A
  single source of truth `core.methodology` — mirrored in the web `lib/perimeter.ts` — maps a
  nomenclature/level to its universe and detects a mixed total. A reusable `MethodologyNote` (DSFR
  info Callout) surfaces the caveat on the Flux Sankey (stronger wording when the traced flow crosses
  universes), the entity Fiche budget totals (local M57 sheets now show realised expenditure instead
  of an empty *voté* figure, attributed to OFGL), and the Graphe table — all linking to an anchored
  `#double-comptage` méthodologie section on the Données page.
- SEM/SPL local public companies connector (FSC-33): an `epl_sem_spl` transform filters a
  SIRENE-derived extract to the SEM/SPL **catégories juridiques** → `level=delegated` entities, and
  emits a `participation` edge (public shareholder → company) **only** when a shareholder is published
  — never inventing a link (golden rule #5); the partial cases (filtered, unresolved, no shareholder)
  are reported. Runs offline against a fixture. The demo seed gains two SEM/SPL companies with
  participation edges from their owning collectivités.
- OFGL local-authority finances connector (FSC-32): a `finances_locales_ofgl` transform turns the
  OFGL *agrégats comptables* (the M57/M14 accounting universe) into **local** entities + `budget_facts`
  keyed on the collectivité SIREN, stamped `nomenclature=m57` — a new `budget_facts.nomenclature`
  column (migration `0006`, default `lolf`) that keeps the State (LOLF) and local accounting universes
  distinct rather than silently summed. Only a curated, mutually-exclusive expenditure agrégat pair is
  ingested (anti-double-counting, golden rule #8); unresolved SIRENs are reported, never guessed. It
  reuses the existing `ods_explore` connector and runs offline against a fixture. The illustrative
  demo seed gains local M57 budgets so a collectivité Fiche renders a budget.
- JSON support in the validate + snapshot harness (FSC-47): `validate_extract` / `write_snapshot`
  now accept `fmt="json"` for tabular JSON (array of records). A registry-driven `records_path`
  (e.g. ODS `results`) unwraps the envelope; the records are tabularised to CSV so the **same**
  proven path enforces the Table Schema (column drift fatal, messy cells warned) and stores an
  `all_varchar` Parquet snapshot with `format='json'` provenance hashing the raw bytes. A malformed
  envelope fails loud; genuinely unsupported formats still raise `UnsupportedFormatError`. Offline
  fixtures cover a valid, a drifted, and an enveloped JSON extract.
- Delivered design screens ported (FSC-50…53): the Accueil overview (hero, headline figures with
  provenance, teaser Sankey, action tiles), the Recherche results + facets, the institutional Graphe
  reworked to a custom **2D-canvas force-directed** layout (clusters, CP-scaled nodes, typed/weighted
  edges, filters, legend, side panel, keyboard nav + synchronized table fallback — superseding the
  Sigma v1), the entity Fiche (budget AE/CP bars + trend, mini-flux, contracts, relations chips), the
  Flux **Sankey** screen, and the Données methodology page. Backed by a separate illustrative
  dev/preview demo seed (`ingestion.demo_seed`) with funds/delegates/participation flows + multi-year
  budgets so the screens render rich data before the flow ingestion (FSC-39/FSC-33) lands. With the
  export fully ported, the `design/` reference folder is removed (it lives on in git history).
- Design system wired app-wide (FSC-49): the delivered `design/` export is adopted as the web app's
  self-contained styling layer — design tokens, the DSFR-faithful base/components, app chrome and
  the self-hosted Marianne fonts under `packages/web/src/styles/`, imported once in `main.tsx`. A
  typed base component library lands in `src/lib/ui/` (icons, Button, Card, Badge/LevelBadge,
  LevelShape, Chip, Callout, Breadcrumb, ExampleFlag, StateBlock, a sortable accessible DataTable)
  plus pure helpers (`format.ts` euro formatters, `levels.ts` the Okabe–Ito level SSOT, `seq.ts`).
  The Marianne header/nav/footer shell is ported to `src/app/shell/` (registry-driven nav with
  per-feature icons + order) and a `/flux` placeholder screen is added so the nav matches the
  design. The committed `design/` folder is the canonical reference for follow-up per-screen tickets.
- State-budget connector + transforms (FSC-26): a generic `ods_explore` connector (Opendatasoft
  Explore v2.1 — resolve the dataset endpoint from the registry, read back the latest exercice and
  fetch *that* year's export filtered via `where=` → validate → snapshot, no frozen URL; bounded,
  fail-loud fetches) plus two per-source transforms turning the
  voted PLF/LFI ("dépenses selon destination") and the monthly execution ("situation mensuelle de
  l'État") into `budget_facts` by mission/programme with AE+CP and a voted/executed flag.
  Anti-double-counting is explicit: PLF sums leaf actions to the programme grain; execution keeps
  the latest (cumulative) month only. `make budget` runs both offline against fixtures. The shared
  `TransformResult` gains a `budget_facts` slice; Supabase loading stays deferred to FSC-35.
- State-operators connector + transform (FSC-25): a generic `datagouv_api` connector
  (discover latest millésime → extract → validate → snapshot, no frozen slug) plus a per-source
  transform turning the *Jaune opérateurs* into `state` entities and `tutelle` (ministry → operator)
  edges. Operator SIRENs resolve via the FSC-23 crosswalk and ministries via a new curated
  `data/crosswalk/ministeres.yaml` (verified ministry SIRENs); edges are emitted only when both ends
  carry a SIREN, unresolved operators are kept and reported (never dropped/guessed). `make operators`
  runs it offline and reports the resolution rate. Supabase loading is deferred to FSC-35.
- Initial repository scaffold, architecture, and Phase-0 spike.
- Ingestion validation + snapshot harness (FSC-16): fail-loud Table Schema validation
  (column/schema drift fatal, messy cells warned) and atomic Parquet snapshots with embedded
  provenance that keep the last valid snapshot on failure. Adds a scheduled-run issue alert.
- Phase-0 live SIREN-match gate (FSC-19): `make spike-live` runs the spike end-to-end against
  live data.gouv.fr (discover → download → validate → snapshot → match), reusing `core.resolve`
  and the ingestion harness. Result recorded in `docs/phase0-siren-match-results.md`:
  **CONDITIONAL GO** — the SIREN join is sound and DECP exposes it abundantly, but the Jaune
  opérateurs list carries no SIREN, so Phase 1 must add a name→SIREN crosswalk first.
