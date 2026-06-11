-- Contract provenance (FSC-31 / FSC-39). Mirrors entities.provenance (0003), edges.provenance
-- (0001) and budget_facts.provenance (0004): the registry source id that contributed the row
-- (here always 'decp_commande_publique'). The curated loader (ingestion.load) rebuilds each table
-- per provenance scope (delete-then-insert by source), so this column is what lets a DECP reload
-- replace only its own contracts without touching other sources' rows. It also lets the contracts
-- table (now loaded from real DECP, not just the seed) be attributed in the provenance UI.
-- Append-only + idempotent; contracts already carries the "public read" RLS policy (0001), which a
-- new column inherits, so no policy or rls_checks change is needed.
alter table contracts add column if not exists provenance text;  -- source id from the registry

-- Index the provenance column the curated loader filters/deletes by on every (scheduled) reload, so
-- provenance-scoped rebuilds stay index scans rather than sequential scans as the table grows.
create index if not exists contracts_provenance_idx on contracts (provenance);
