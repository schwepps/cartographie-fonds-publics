-- supabase/seed.sql — committed curated seed (FSC-24). GENERATED, do not edit by hand:
-- regenerate with `make seed` (source: packages/ingestion/src/ingestion/seed.py).
--
-- A tiny, real, licence-attributed État-central slice so a fresh dev DB and Vercel previews render
-- a populated graph + entity sheet without the full ingestion load (FSC-35). DEV/PREVIEW ONLY —
-- never apply to the curated production database (it truncates the curated tables first).
--
-- Provenance & licence (all Licence Ouverte / Etalab 2.0):
--   * Ministries, operators, tutelle edges — resolved from data/crosswalk/*.yaml (Jaune
--     « Opérateurs de l'État », Direction du budget; ministry SIRENs verified via
--     recherche-entreprises, nature juridique 7113).
--   * Budget facts — PLF 2025, mission MIRES, voté (programmes 150 & 172). Source: Sénat, rapport
--     général PLF 2025 — Recherche et enseignement supérieur
--     (https://www.senat.fr/rap/l24-144-324/l24-144-324_mono.html) + budget.gouv.fr PAP.
--   * Contracts — DECP consolidées (DAJ/Etalab), data.gouv.fr resource
--     22847056-61df-452d-837d-8b8ceadbfc52 (extrait 2026-06-09).


begin;

-- Idempotent: clear the curated tables, then re-insert the seed slice.
truncate entities, edges, budget_facts, contracts, attributions, mentions restart identity cascade;

-- Entities: ministries (graph roots) then operators.
insert into entities (siren, name, level, category, parent_siren, provenance) values
  ('110000072', 'Ministère du Travail et des Solidarités', 'state', 'ministère', null, 'operateurs_etat'),
  ('110044013', 'Ministère de l''Enseignement supérieur et de la Recherche', 'state', 'ministère', null, 'operateurs_etat'),
  ('110046018', 'Ministère de la Culture', 'state', 'ministère', null, 'operateurs_etat'),
  ('130005481', 'France Travail', 'state', null, '110000072', 'operateurs_etat'),
  ('180046252', 'Bibliothèque nationale de France', 'state', 'EPA', '110046018', 'operateurs_etat'),
  ('180089013', 'Centre national de la recherche scientifique', 'state', 'EPST', '110044013', 'operateurs_etat');

-- Tutelle edges: ministry -> operator.
insert into edges (source_siren, target_siren, type, amount_eur, exercice, provenance) values
  ('110000072', '130005481', 'tutelle', null, null, 'operateurs_etat'),
  ('110044013', '180089013', 'tutelle', null, null, 'operateurs_etat'),
  ('110046018', '180046252', 'tutelle', null, null, 'operateurs_etat');

-- Budget facts: PLF 2025 MIRES, voté (mission/programme grain).
insert into budget_facts (entity_siren, exercice, mission, programme, amount_ae_eur, amount_cp_eur, executed) values
  (null, 2025, 'MIRES', '150', 15217000000, 15279000000, false),
  (null, 2025, 'MIRES', '172', 8259807441, 8701105312, false);

-- Contracts: real DECP marchés (CNRS acheteur).
insert into contracts (acheteur_siren, titulaire_siren, montant_eur, nature, exercice) values
  ('180089013', '329200521', 1800000, 'marche', 2026),
  ('180089013', '326556578', 84925.39, 'marche', 2026);


commit;
