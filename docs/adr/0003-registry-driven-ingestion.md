# 3. Registry-driven, schema-validated ingestion

- Status: accepted
- Date: 2026-06-08

## Context
Open data sources drift: annual re-slugging (PLF), deprecated datasets (DECP),
URL migrations (service-public.fr -> .gouv.fr). Hardcoding source locations makes
the project unmaintainable.

## Decision
A single source of truth, `data/registry/sources-registry.yaml`, drives all
ingestion. Connectors **discover** datasets via the data.gouv.fr `/api/1` catalog
(organisation + tag + millesime), never via frozen slugs. Every extract is
validated against its schema (schema.data.gouv.fr / Table Schema) and **fails
loud** on drift. Raw extracts are snapshotted with provenance.

## Consequences
Adding or fixing a source is usually a one-line registry edit. Drift becomes a
detected signal, not a silent break.
