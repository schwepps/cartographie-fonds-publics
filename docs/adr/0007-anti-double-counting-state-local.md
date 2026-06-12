# 7. Anti-double-counting across accounting universes (State ↔ local)

- Status: accepted
- Date: 2026-06-11

## Context
French public money is recorded in several **accounting universes** that are not consolidatable into
one figure:

- **État (LOLF)** — the State budget: mission > programme > action, with *autorisations
  d'engagement* (AE) and *crédits de paiement* (CP). Sources: `budget_plf_lfi`,
  `budget_execution_mensuelle`.
- **Collectivités (M57/M14)** — local-authority accounts, published by the OFGL as normalised
  *agrégats* on a cash basis. Source: `finances_locales_ofgl` (FSC-32).
- **Sécurité sociale (LFSS)** — social-security accounts, a separate perimeter again.

Two distinct double-counting risks follow:

1. **Across universes.** The same public effort is recorded in more than one universe (e.g. a State
   transfer that a collectivité then re-spends). Summing a State LOLF total with a local M57 total is
   not a consolidated figure — it double-counts and mixes incompatible conventions (AE/CP vs cash).
2. **Across hops of a funding chain.** A euro is counted as a subvention (financeur → opérateur) and
   again as that operator's onward spend (opérateur → titulaire/délégataire).

This becomes live once the local layer (OFGL) joins the State layer.

## Decision
Make the perimeter **explicit** rather than netting silently (golden rule #8):

- Each `budget_facts` row carries a `nomenclature` (`lolf` / `m57` / `m14` / `social`, migration
  `0006`) — the accounting universe is a first-class column, not inferred from a provenance string.
- A single source of truth, `core.methodology`, maps a nomenclature (and, for the browser, an entity
  `level`) to its universe and exposes `mixes_perimeters(...)`. The web mirrors it in
  `lib/perimeter.ts` (keyed on `level`, the in-browser proxy).
- **Within** a universe we aggregate at that source's documented grain: PLF sums leaf actions to the
  programme grain; DECP collapses a market to its current attribution and splits the montant equally
  among co-titulaires before summing; OFGL ingests only a curated, mutually-exclusive expenditure
  agrégat pair (fonctionnement + investissement).
- **Across** universes (or across funding hops) we **do not consolidate**. A total that spans
  universes is presented as an order of magnitude and **always carries a visible methodology note**
  (`MethodologyNote`, linking to `/sources#double-comptage`) wherever it appears — the Flux Sankey,
  the entity Fiche budget totals, and the Graphe totals.

## Consequences
Mixed-perimeter totals are never silently presented as consolidated sums; the caveat is enforced in
one place (`core.methodology` / `lib/perimeter.ts`) and surfaced consistently in the UI. Adding a new
universe (e.g. APU, a finer social breakdown) is a mapping edit plus, if it is a new `budget_facts`
nomenclature, a `CHECK`-constraint migration — not a change to every aggregation site.

## Verification (FSC-58)
The convention is proven on combined, multi-universe data, not only documented:

- `core.methodology.perimeter_totals(facts)` is the canonical per-universe breakdown — its keys
  **partition** the facts, so the values never double-count across universes (it is deliberately not
  a consolidated total). `tests/test_methodology.py` checks the partition is exact, that a combined
  set is flagged `mixes_perimeters`, and that a State→local transfer `Edge` cannot enter a universe
  total (it is a flow, not a `budget_facts` row).
- `packages/ingestion/tests/test_reconciliation.py` builds the **real merged 4-layer bundle** offline
  (`build_bundle(ALL_SOURCE_IDS)`) and reconciles it: the per-universe sums partition the grand CP
  total exactly, LOLF voted vs executed are kept separate (the residual is named, the headline filters
  to voted), and the delegation hop (contracts) is disjoint from the budget universes.
- `test_pipeline_integration.py` (FSC-57) adds the same reconciliation on the **actually-loaded**
  Postgres graph (every fact carries a universe; per-universe sums reconcile to the grand total; the
  breakdown is logged so any residual is visible, not hidden).
- The web `perimetre` view is asserted to never render a consolidated cross-universe figure and to
  state the non-consolidation convention.
