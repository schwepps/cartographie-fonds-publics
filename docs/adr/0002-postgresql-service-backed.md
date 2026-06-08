# 2. PostgreSQL, service-backed from day one

- Status: superseded by [ADR-0005](0005-supabase-vercel-baas.md)
- Date: 2026-06-08

## Context
The product must answer relationship questions ("who funds/oversees whom") and
serve interactive exploration. A static build was considered but rejected for the
MVP because live querying and filtering are core to the value.

## Decision
FastAPI + PostgreSQL. Model the institutional graph relationally (entities + typed
edges) and traverse with recursive CTEs. Heavy analytical staging uses DuckDB /
Parquet during ingestion; curated facts and edges are loaded into Postgres.

## Consequences
- More ops than a static site (a DB to host) — acceptable for the goals.
- If deep multi-hop graph traversal becomes a bottleneck, revisit with the
  Postgres **Apache AGE** extension or a dedicated graph DB (new ADR).
