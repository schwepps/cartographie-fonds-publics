# Phase-0 Go/No-Go — SIREN match rate on live data (FSC-19)

**Run date:** 2026-06-08 (UTC) · **Mode:** `make spike-live` (live data.gouv.fr `/api/1`)
**Verdict:** 🟡 **CONDITIONAL GO** — the SIREN join is sound, but the operators source carries
no SIREN, so Phase 1 must add a name→SIREN crosswalk *before* wiring operators into DECP.

This is the project's key risk gate: can French State operators be joined to public procurement
(DECP) on SIREN? The spike discovers both datasets live (no hardcoded slug), downloads, validates,
snapshots, and computes the match. Reproduce with `make spike-live`; the machine summary is written
to `spikes/phase0_siren_match/out/phase0_live_summary.json`.

## What the live run found

### Operators — "Jaune opérateurs de l'État" (PLF 2026)
- Discovered via catalog query `"jaune opérateurs de l'État"` → dataset
  `projet-de-loi-de-finances-pour-2026-...-jaune-operateurs-...` (id `69665c766034b48d897c47be`),
  resolved as the latest millésime with **no hardcoded slug**.
- Resource `plf2026-jauneoperateurs.csv` (cp1252, transcoded to UTF-8), **431 rows**.
- Columns: `Opérateur ou catégorie d'opérateurs`, `Opérateur de la catégorie`, `Statut`,
  `Mission et Programme chefs de file`, `PLF`.
- **No SIREN column at all → SIREN coverage = 0%.**

### DECP — "Données essentielles de la commande publique consolidées (format tabulaire)"
- Discovered via `"données essentielles commande publique consolidées"` → dataset
  id `608c055b35eb4e6ee20eb325`. Primary CSV `decp.csv` is **~2 184 MB**; the spike bounded the
  download to a **50 MB head sample = 65 756 rows** (the small annex CSVs
  `probabilites-naf-cpv.csv` / `statistiques-sources.csv` are correctly ignored).
- Buyer column `acheteur_id` → **5 463 distinct SIRENs**; supplier column `titulaire_id` →
  **21 990 distinct SIRENs** (27 347 combined). Parties are identified by **SIRET**; the canonical
  SIREN is its first 9 digits.

### Match rate
| Metric | Result |
| --- | --- |
| Operator SIREN coverage (live) | **0%** (431 rows, no SIREN field) |
| Match vs DECP buyers / suppliers / either | **0% / 0% / 0%** (structural — empty operator side) |
| Offline sample match (proves the join mechanics) | **60%** of resolvable operators (`make spike`) |

The live match is 0% **by construction**, not because SIREN fails as a key: the operators side has
no SIREN to join on. The DECP side exposes the key abundantly, and the offline sample confirms the
join works whenever SIRENs are present.

## Go/No-Go decision

**CONDITIONAL GO.** SIREN is a viable join key for the institutional graph, on one condition:

- **Named gap:** the *Jaune opérateurs* list — the graph's seed of ~430 operators — publishes **no
  SIREN** (only dénomination, statut, tutelle/programme).
- **Required mitigation (Phase-1 prerequisite):** resolve operator **dénomination + tutelle →
  SIREN** via a *reviewed* crosswalk against SIRENE / the
  [`annuaire_administration`](../data/registry/sources-registry.yaml) source. Per golden rule #5:
  never guess, never silently drop — unresolved operators go to the reviewed crosswalk, and the
  **match rate is reported**. Only after this step does the operators→DECP SIREN join light up.

Until the crosswalk exists, the operators→DECP match rate is structurally 0, so this gate is **not a
clean pass**: the spike exits non-zero (`1`) to signal "needs work before Phase 1".

> **Follow-up — measured GO.** [FSC-48](phase0_5-operator-resolution-results.md) sized that crosswalk:
> **66 %** of the ~430 operators auto-resolve to a SIREN by name (recherche-entreprises / SIRENE),
> leaving a bounded **146-operator** manual backlog. The CONDITIONAL GO above is now a measured
> **PROCEED TO PHASE 1**.

## Findings carried into Phase 1
1. **Operators have no SIREN** → build the name-match crosswalk first (the single biggest Phase-1
   dependency). The DECP join itself is low-risk.
2. **DECP identifies parties by SIRET** → derive SIREN as the first 9 digits (canonical).
3. **French open-data CSVs are cp1252/latin-1**, but the snapshot harness (duckdb) is UTF-8-only →
   the connector must declare/transcode source encoding.
4. **DECP `schema.ref` points at the portal root** (registry TODO, FSC-16 follow-up) → real
   TableSchema validation is still pending; point it at the DECP TableSchema JSON.
5. **DECP is a single ~2 GB file** (no small partitions) → ingestion must stream/partition it; the
   spike samples the head only.

## Methodology & caveats
- Match computed on a **bounded 50 MB head sample** of DECP, not the full 2 GB file — sufficient to
  prove the join key is present, not a population estimate.
- Raw extracts snapshotted to Parquet with provenance under `data/snapshots/<source_id>/`
  (gitignored). Numbers above are reproducible via `make spike-live`; live figures shift as
  data.gouv.fr publishes new millésimes.
