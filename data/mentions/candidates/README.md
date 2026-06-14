# Cour des comptes mention candidates (FSC-67)

Auto-generated **review backlog** for the « contrôle » layer — report→entity links extracted from
report full text. **Never auto-loaded.** The published source of truth stays the reviewed
`../cour_des_comptes.yaml`; a human promotes vetted candidates into it.

Produced by `make extract-mentions` (→ `transforms/cour_des_comptes_extract.py`): each report PDF is
downloaded directly (not the snapshot layer — PDFs are non-tabular, FSC-38), parsed to text with
`pypdf`, and scanned for known entity names/acronyms from the reviewed crosswalk
(`../../crosswalk/operateurs.yaml`) + ministry reference (`../../crosswalk/ministeres.yaml`).

## How it links (deterministic, precision-first)

This is **not** ML/NER — it is a transparent gazetteer matcher, so it is offline-testable and never
guesses a SIREN (golden rule #5):

- A name resolves only when it matches an **accepted** crosswalk/ministry entry (which carries a
  verified SIREN). A hit on a `pending` entry → `resolution_status: unresolved` (backlog, no SIREN).
- **Precision guards**: a denomination surface must carry ≥ 2 distinctive tokens (drops bare
  "Agence"); an acronym must be all-caps and ≥ 3 chars; matches are **word-boundary** anchored
  ("Agence Alpha" never matches inside "Agence Alphabet"); a surface that maps to two different
  SIRENs is dropped (ambiguous → never guess).
- **Curated aliases (FSC-70)**: a crosswalk/ministry row may carry an `aliases` list (former names,
  common acronyms — e.g. `France Travail` → « Pôle emploi »). Each alias is added to the gazetteer as
  one more **exact-match** surface, run through the very same precision guards. This widens recall over
  entities we already track without ever softening to fuzzy matching. Add aliases by hand on a
  `reviewed` row in `../../crosswalk/operateurs.yaml` / `../../crosswalk/ministeres.yaml`.
- **Recall limit (deliberate)**: an entity *absent* from the crosswalk cannot be auto-detected here.
  Such names are only added via the editorial path. The gazetteer scales coverage over entities we
  already track, with high precision.

## Schema

`cour_des_comptes_candidates.yaml`:

```yaml
schema_version: 1
candidates:
  - entity_denomination: Centre national de la recherche scientifique
    entity_siren: "180088407"          # null for an unresolved (pending) entity
    report_ref: Le CNRS — exercices 2018-2023
    report_date: "2025-03-25"
    mention_type: rapport               # rapport | recommandation
    url: https://www.ccomptes.fr/fr/publications/...
    note: "…excerpt around the first match (reviewer evidence)…"
    match_count: 4                      # times the entity was named (precision signal)
    resolution_status: resolved         # resolved | unresolved
    provenance: cour_des_comptes
    license: Licence Ouverte 2.0
```

## Promotion (human-in-the-loop)

A mention is a public-trust signal — precision over recall. To publish a candidate:

1. Open its `url` and confirm the report genuinely épingle the entity (not a passing mention).
2. Copy `entity_denomination`, `report_ref`, `report_date`, `mention_type`, `url`, `note` into
   `../cour_des_comptes.yaml`. The SIREN is re-resolved at build time — do **not** carry it over.
3. For an `unresolved` row, first resolve the entity in `../../crosswalk/operateurs.yaml` (promote
   its `pending` row to `reviewed` with a verified SIREN), then promote the mention.

Only after promotion does the mention render on the fiche (« Contrôle / Cour des comptes ») and the
graph badge (« épinglé par la Cour », FSC-65).

## Running on the real corpus (operator) + deferred robustness (FSC-70)

To scale beyond the demonstrable subset:

1. Assemble a reports list (`reports:` of `{url, report_ref, report_date, mention_type, license}`)
   from the data.gouv `cour-des-comptes` corpus (and CRTC regional reports).
2. Run `make extract-mentions REPORTS=path/to/reports.yaml`; review coverage + match rate.
3. Promote vetted candidates into `../cour_des_comptes.yaml` per the flow above (precision over recall).

**Deferred to their own PRs** (each needs the live corpus to tune precision/recall, so they are not
landed blind): **OCR fallback** for scanned/image PDFs (today `extract_text` is fail-loud, no OCR);
**fuzzy/near-match** routing of low-confidence hits to the backlog (the gazetteer is exact-match by
design). Curated `aliases` (above) are the precision-preserving recall lever available today.
