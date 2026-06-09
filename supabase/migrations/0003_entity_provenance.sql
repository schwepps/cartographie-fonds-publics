-- Entity-level provenance (FSC-28). Mirrors edges.provenance: the registry source id
-- that contributed the entity, so the UI can attribute each entity to its open-data source.
-- Append-only + idempotent; entities already carries the "public read" RLS policy, which a
-- new column inherits, so no policy or rls_checks change is needed.
alter table entities add column if not exists provenance text;  -- source id from the registry
