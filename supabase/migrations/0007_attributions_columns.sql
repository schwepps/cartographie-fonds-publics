-- Attributions enrichment (FSC-27). The table was scaffolded minimally in 0001 (entity_siren,
-- legal_ref, txt). The "why" layer needs two more business columns:
--   * source_url — the real Légifrance/JORF link that backs the legal reference (golden rule #10:
--     every mandate links to a verifiable source; the entity-sheet section renders it as a link);
--   * provenance — the registry source id that contributed the row (here 'legifrance_attributions').
--     The curated loader (ingestion.load) rebuilds each table per provenance scope (delete-then-
--     insert by source), so this column is what lets an attributions reload replace only its own
--     rows, exactly like edges/budget_facts/contracts (0001/0004/0005). It also lets the row be
--     attributed in the provenance UI.
-- Append-only + idempotent; attributions already carries the "public read" RLS policy (0001), which
-- a new column inherits, so no policy or rls_checks change is needed.
alter table attributions add column if not exists source_url text;  -- Légifrance/JORF URL
alter table attributions add column if not exists provenance text;  -- source id from the registry

-- Backfill any pre-existing rows. The loader rebuilds attributions per provenance scope, so a
-- NULL-provenance row would fall outside every delete scope and accumulate across reloads.
-- legifrance_attributions is the only writer of this table, so stamp that source. (The loader fails
-- loud on a NULL provenance, so no new NULLs are introduced; the column stays nullable to mirror
-- entities/edges/budget_facts/contracts.provenance.)
update attributions set provenance = 'legifrance_attributions' where provenance is null;

-- Index the columns the loader filters/deletes by (provenance) and the fiche queries by
-- (entity_siren), so provenance-scoped rebuilds and entity-sheet reads stay index scans.
create index if not exists attributions_provenance_idx on attributions (provenance);
create index if not exists attributions_entity_idx on attributions (entity_siren);
