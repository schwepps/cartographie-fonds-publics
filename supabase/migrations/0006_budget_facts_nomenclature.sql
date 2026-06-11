-- Budget-fact accounting nomenclature (FSC-32 / FSC-42). State budget facts follow LOLF
-- (mission/programme, AE/CP); OFGL local facts follow the M57/M14 universe (agrégats, cash basis);
-- social-security accounts are a third perimeter. This column makes the accounting universe
-- explicit so the anti-double-counting methodology (FSC-42) can flag a total that *mixes* universes,
-- rather than inferring the perimeter from provenance strings.
--
-- Existing rows backfill to 'lolf' (every fact so far is State-budget). Append-only + idempotent;
-- budget_facts already carries the "public read" RLS policy, which a new column inherits — so no
-- policy or rls_checks change is needed (mirrors 0004_budget_facts_provenance).
alter table budget_facts
  add column if not exists nomenclature text not null default 'lolf'
  check (nomenclature in ('lolf', 'm57', 'm14', 'social'));
