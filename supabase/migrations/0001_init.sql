-- Curated graph + aggregates for the UI. (Supabase Pro = 8 GB; keeping raw dumps
-- out of Postgres as Parquet remains good practice, not a hard limit.)
create extension if not exists pgcrypto;  -- gen_random_uuid()

create table if not exists entities (
  id           uuid primary key default gen_random_uuid(),
  siren        text unique,                -- canonical key; null until resolved
  name         text not null,
  level        text not null check (level in ('state','local','social','delegated')),
  category     text,
  parent_siren text
);

create table if not exists edges (
  id           uuid primary key default gen_random_uuid(),
  source_siren text not null,
  target_siren text not null,
  type         text not null check (type in ('tutelle','participation','funds','delegates')),
  amount_eur   numeric,
  exercice     int,
  provenance   text                        -- source id from the registry
);
create index if not exists edges_source_idx on edges (source_siren);
create index if not exists edges_target_idx on edges (target_siren);

create table if not exists budget_facts (
  id            uuid primary key default gen_random_uuid(),
  entity_siren  text,
  exercice      int not null,
  mission       text,
  programme     text,
  amount_ae_eur numeric,
  amount_cp_eur numeric,
  executed      boolean not null default false
);
create index if not exists budget_entity_idx on budget_facts (entity_siren, exercice);

create table if not exists contracts (
  id              uuid primary key default gen_random_uuid(),
  acheteur_siren  text,
  titulaire_siren text,
  montant_eur     numeric,
  nature          text check (nature in ('marche','concession')),
  exercice        int
);
create index if not exists contracts_buyer_idx on contracts (acheteur_siren);

create table if not exists attributions (
  id uuid primary key default gen_random_uuid(),
  entity_siren text, legal_ref text, txt text
);
create table if not exists mentions (
  id uuid primary key default gen_random_uuid(),
  entity_siren text, report_ref text, note text
);

-- RLS: public read-only. Writes use the service-role key (ingestion), which bypasses RLS.
do $$
declare t text;
begin
  foreach t in array array['entities','edges','budget_facts','contracts','attributions','mentions']
  loop
    execute format('alter table %I enable row level security;', t);
    execute format($p$create policy "public read" on %I for select to anon, authenticated using (true);$p$, t);
  end loop;
end $$;
