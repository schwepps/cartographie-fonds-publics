# Changelog

All notable changes to this project are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/), versioning: [SemVer](https://semver.org/).
Commits follow [Conventional Commits](https://www.conventionalcommits.org/).

## [Unreleased]
### Added
- Initial repository scaffold, architecture, and Phase-0 spike.
- Ingestion validation + snapshot harness (FSC-16): fail-loud Table Schema validation
  (column/schema drift fatal, messy cells warned) and atomic Parquet snapshots with embedded
  provenance that keep the last valid snapshot on failure. Adds a scheduled-run issue alert.
- Phase-0 live SIREN-match gate (FSC-19): `make spike-live` runs the spike end-to-end against
  live data.gouv.fr (discover → download → validate → snapshot → match), reusing `core.resolve`
  and the ingestion harness. Result recorded in `docs/phase0-siren-match-results.md`:
  **CONDITIONAL GO** — the SIREN join is sound and DECP exposes it abundantly, but the Jaune
  opérateurs list carries no SIREN, so Phase 1 must add a name→SIREN crosswalk first.
