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
