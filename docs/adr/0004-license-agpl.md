# 4. License: AGPL-3.0-or-later

- Status: accepted
- Date: 2026-06-08

## Context
This is a public-interest transparency **application** (hosted service), not an
embeddable library. We want improvements to stay in the commons, including for
hosted/modified deployments.

## Decision
License the application under **AGPL-3.0-or-later**. The AGPL network clause
requires anyone offering a modified version as a service to publish their source.

## Consequences
- Strong protection of the commons; standard for civic-tech platforms.
- May deter some closed-source commercial reuse (accepted trade-off).
- **Exception:** any sub-package later extracted as a reusable library (e.g. the
  ingestion connectors) MAY be relicensed permissively (MIT) to maximise reuse —
  record as a new ADR when it happens.
