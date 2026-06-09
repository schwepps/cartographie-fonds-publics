-- Budget-fact provenance (FSC-35). Mirrors entities.provenance (0003) and edges.provenance:
-- the registry source id that contributed the fact (e.g. 'budget_plf_lfi',
-- 'budget_execution_mensuelle'). The curated loader rebuilds each table per provenance scope
-- (delete-then-insert by source), so this column is what lets a State-budget reload replace only
-- its own facts without touching other sources' rows. Also feeds the FSC-28 attribution UI and the
-- FSC-43 ingestion run summary.
-- Append-only + idempotent; budget_facts already carries the "public read" RLS policy, which a new
-- column inherits, so no policy or rls_checks change is needed.
alter table budget_facts add column if not exists provenance text;  -- source id from the registry
