# Changelog

All notable changes to this project are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/), versioning: [SemVer](https://semver.org/).
Commits follow [Conventional Commits](https://www.conventionalcommits.org/).

## [Unreleased]
### Added
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
