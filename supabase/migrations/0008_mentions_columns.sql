-- Mentions enrichment (FSC-62). The table was scaffolded minimally in 0001 (entity_siren,
-- report_ref, note). The Cour des comptes oversight layer (« épinglé par la Cour ») needs the
-- metadata-first fields the fiche section renders, plus provenance for the loader:
--   * report_date  — publication date (carried as text, like other dates in the curated graph);
--   * mention_type — 'rapport' | 'recommandation' (CHECK mirrors the core MentionType enum);
--   * url          — the source report link (rendered as an external link on the fiche);
--   * provenance   — registry source id ('cour_des_comptes'); the loader rebuilds per provenance
--                    scope (delete-then-insert), so this is what scopes a mentions reload, exactly
--                    like edges/budget_facts/contracts (0001/0004/0005);
--   * license      — per-row licence: the audit corpus is NOT uniformly licensed (the published-
--                    recommendations dataset is ODbL, not the registry's default Licence Ouverte),
--                    so licence is captured per mention, not assumed from the source.
-- The existing `note` column is kept as the short excerpt. Append-only + idempotent; mentions
-- already carries the "public read" RLS policy (0001), which new columns inherit — no policy or
-- rls_checks change needed.
alter table mentions add column if not exists report_date  text;
alter table mentions add column if not exists mention_type text
  check (mention_type in ('rapport','recommandation'));
alter table mentions add column if not exists url          text;
alter table mentions add column if not exists provenance   text;  -- source id from the registry
alter table mentions add column if not exists license      text;  -- per-row licence (corpus varies)

-- Backfill any pre-existing rows (see the attributions migration for why a NULL provenance breaks
-- provenance-scoped reloads). cour_des_comptes is the only writer of this table.
update mentions set provenance = 'cour_des_comptes' where provenance is null;

-- Index the columns the loader deletes by (provenance) and the fiche queries by (entity_siren).
create index if not exists mentions_provenance_idx on mentions (provenance);
create index if not exists mentions_entity_idx on mentions (entity_siren);
