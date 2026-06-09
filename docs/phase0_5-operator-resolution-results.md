# Phase-0.5 — Operator name→SIREN auto-resolution rate (FSC-48)

**Run date:** 2026-06-09 (UTC) · **Mode:** `make spike-resolve-live`
**Verdict:** 🟢 **PROCEED TO PHASE 1** — **66 %** of the ~430 State operators auto-resolve to a
SIREN from their name alone; the residual **146-operator** backlog is bounded and tractable for
the reviewed crosswalk (FSC-23).

This spike answers the single number [FSC-19](phase0-siren-match-results.md) left open. FSC-19
proved the SIREN join is sound but found the *Jaune opérateurs* list carries **no SIREN** (0 %
coverage), making it a *CONDITIONAL GO*. The mitigation is a reviewed name→SIREN crosswalk —
so before building it (FSC-23) and the operators connector (FSC-25), we measured **how much of
that crosswalk is automatic**. Reproduce with `make spike-resolve-live`; the machine summary is
written to `spikes/phase0_siren_match/out/phase0_5_resolution_summary.json` and a per-operator
crosswalk to `out/operator_resolution.csv`.

## Method

- **Source operators:** the live *Jaune opérateurs de l'État* (PLF 2026) dataset, discovered via
  the registry (`operateurs_etat`) with **no hardcoded slug** (id `69665c766034b48d897c47be`,
  431 rows). The operator name is `coalesce(leaf "Opérateur de la catégorie", grouping "Opérateur
  ou catégorie d'opérateurs")` — either column alone drops ~165 of 431 rows.
- **Resolver:** the public **recherche-entreprises** API (SIRENE-backed, no token, ~7 req/s). Its
  base URL lives in the registry (`recherche_entreprises` source) — never hardcoded (golden rules
  #1/#2). One full-text query per operator.
- **Matching is conservative (golden rule #5 — never guess):** a candidate is accepted **only on
  exact normalized-name equality** (accent-/case-folded, articles + bare legal forms stripped). A
  known `ACRONYM - Full name` prefix (e.g. *"IGN - Institut national…"*) is stripped before the
  equality test — a deterministic formatting fix, **not** a fuzzy guess. `tutelle` is used only as
  a soft public-sector tie-breaker (`est_administration` / public legal category); a tutelle-code→
  entity map is deferred to FSC-23.
- **Three ambiguity tiers:** `unique` (exactly one SIREN, after the soft filter) → auto-accepted;
  `multiple` (>1 exact-name SIREN the filter can't reduce) → crosswalk; `none` (no exact match) →
  crosswalk. **Resolution rate = unique / total.**

## What the live run found

### Resolution (431 operators)
| Tier | Count | Share |
| --- | --- | --- |
| **unique** (auto-resolved → SIREN) | **285** | **66 %** |
| multiple (ambiguous, routed to crosswalk) | 13 | 3 % |
| none (unmatched, routed to crosswalk) | 133 | 31 % |
| **Manual-curation backlog (FSC-23)** | **146** | **34 %** |

Spot-checks confirm the accepted matches are correct (ADEME → `385290309`, AEFE → `180006082`,
ANACT → `180037012`, …); **80** of the 285 were resolved from an `ACRONYM - Name` entry once the
prefix was stripped. The 13 `multiple` cases are genuine namesakes (e.g. *École Normale Supérieure*
→ 3 candidates, *ANR* → 2) and are deliberately **not** guessed.

### Operator→DECP appearance (closes FSC-19's structural 0 %)
Of the 285 resolved operators, **101 (35 %)** appear as an `acheteur` or `titulaire` in a bounded
50 MB head sample of the consolidated DECP (id `608c055b35eb4e6ee20eb325`; 27 347 distinct
buyer/supplier SIRENs in the sample). FSC-19 reported 0 % here purely because the operator side had
no SIREN; with SIRENs resolved, the operators→DECP join lights up — on a *head sample*, so 35 % is a
presence signal, not a population estimate (the full 2 GB join should raise it).

## Go/No-Go decision

**PROCEED TO PHASE 1.** A two-thirds automatic crosswalk turns FSC-19's *CONDITIONAL GO* into a
measured **GO**:

- The name→SIREN crosswalk is **mostly automatic** (66 %), so FSC-23 is a *review-and-fill* effort,
  not a build-from-scratch one.
- The residual backlog is **bounded at 146 operators** (13 ambiguous + 133 unmatched) — a tractable,
  one-time manual-review set, not an open-ended problem. The per-operator `out/operator_resolution.csv`
  (tier, candidate SIREN(s), confidence, DECP appearance) **is** that backlog, made concrete.
- Unmatched operators are dominated by abbreviated all-caps leaf names (CROUS, *Communautés
  d'universités*, single *écoles*) whose SIRENE legal name differs more than a prefix — exactly the
  hard cases a reviewed crosswalk exists for.

## Findings carried into Phase 1 (FSC-23 / FSC-25)
1. **66 % auto-resolves** → seed the crosswalk from `out/operator_resolution.csv`; reviewers focus on
   the 146 `multiple` + `none` rows, ordered by `top_match_ratio`.
2. **`ACRONYM - Full name` is the dominant Jaune format** → the connector should normalize it; it
   alone recovered 80 operators.
3. **Ambiguous namesakes need a disambiguator** → the `tutelle`/mission column is present; a proper
   tutelle-code→entity map (deferred here) would resolve most `multiple` cases.
4. **`recherche_entreprises` is a viable token-free resolver** → added to the registry; FSC-25 can
   reuse it for connector-time resolution with provenance.

## Methodology & caveats
- Auto-acceptance uses **exact normalized-name equality only** — never fuzzy. `top_match_ratio`
  (difflib) is recorded for the backlog rows as a reviewer hint, never to accept.
- A handful of pure category labels (e.g. *"Universités et assimilés"*) have no own SIREN and land in
  the backlog by design.
- DECP appearance is measured on a **bounded 50 MB head sample** of the ~2 GB consolidated CSV.
- Live figures shift as data.gouv.fr publishes new millésimes and as SIRENE updates; raw extracts are
  snapshotted to Parquet with provenance under `data/snapshots/<source_id>/` (gitignored).
