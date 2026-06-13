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
--   * Budget facts — PLF 2025, mission MIRES, voté (programmes 150 & 172), attributed to the
--     owning ministry MESR (the budget holder; SIREN resolved from the ministry reference).
--     Source: Sénat, rapport général PLF 2025 — Recherche et enseignement supérieur
--     (https://www.senat.fr/rap/l24-144-324/l24-144-324_mono.html) + budget.gouv.fr PAP.
--   * Contracts — DECP consolidées (DAJ/Etalab), data.gouv.fr resource
--     22847056-61df-452d-837d-8b8ceadbfc52 (extrait 2026-06-09).
--   * Attributions — décrets d'attribution (Légifrance/JORF, DILA); resolved to the ministry
--     SIREN via data/crosswalk/ministeres.yaml. Source: data/attributions/ministres.yaml (FSC-27).
--   * Mentions — Cour des comptes publications (ccomptes.fr), linked to the entity SIREN via the
--     reviewed mapping data/mentions/cour_des_comptes.yaml (FSC-62).


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

-- Edges: tutelle (ministry -> operator) + delegates (acheteur -> titulaire, from DECP).
insert into edges (source_siren, target_siren, type, amount_eur, exercice, provenance) values
  ('180089013', '326556578', 'delegates', 84925.39, 2026, 'decp_commande_publique'),
  ('180089013', '329200521', 'delegates', 1800000, 2026, 'decp_commande_publique'),
  ('110000072', '130005481', 'tutelle', null, null, 'operateurs_etat'),
  ('110044013', '180089013', 'tutelle', null, null, 'operateurs_etat'),
  ('110046018', '180046252', 'tutelle', null, null, 'operateurs_etat');

-- Budget facts: PLF 2025 MIRES, voté (mission/programme grain).
insert into budget_facts (entity_siren, exercice, mission, programme, amount_ae_eur, amount_cp_eur, executed, nomenclature, provenance) values
  ('110044013', 2025, 'MIRES', '150', 15217000000, 15279000000, false, 'lolf', 'budget_plf_lfi'),
  ('110044013', 2025, 'MIRES', '172', 8259807441, 8701105312, false, 'lolf', 'budget_plf_lfi');

-- Contracts: real DECP marchés (CNRS acheteur).
insert into contracts (acheteur_siren, titulaire_siren, montant_eur, nature, exercice, provenance) values
  ('180089013', '329200521', 1800000, 'marche', 2026, 'decp_commande_publique'),
  ('180089013', '326556578', 84925.39, 'marche', 2026, 'decp_commande_publique');

-- Attributions: real décrets d'attribution on seeded ministries (FSC-27).
insert into attributions (entity_siren, legal_ref, txt, source_url, provenance) values
  ('110000072', 'Décret n° 2025-1001 du 29 octobre 2025 relatif aux attributions du ministre du travail et des solidarités', 'Le ministre du travail et des solidarités prépare et met en œuvre la politique du Gouvernement dans les domaines du travail, de l''emploi, de l''insertion professionnelle, de l''apprentissage, de la formation professionnelle, du dialogue social et de la solidarité.', 'https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000052456634', 'legifrance_attributions'),
  ('110044013', 'Décret n° 2025-1021 du 29 octobre 2025 relatif aux attributions du ministre de l''enseignement supérieur, de la recherche et de l''espace', 'Le ministre prépare et met en œuvre la politique du Gouvernement en matière d''enseignement supérieur, de vie étudiante, de recherche, de technologie et d''espace civil.', 'https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000052457282', 'legifrance_attributions'),
  ('110046018', 'Décret n° 2025-1016 du 29 octobre 2025 relatif aux attributions du ministre de la culture', 'Le ministre de la culture conduit la politique de sauvegarde, de protection et de mise en valeur du patrimoine, favorise la création et la diffusion des œuvres, l''accès de tous à la culture, les enseignements artistiques, les médias et les industries culturelles, et le rayonnement culturel de la France.', 'https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000052457068', 'legifrance_attributions');

-- Mentions: real Cour des comptes publications on seeded entities (FSC-62).
insert into mentions (entity_siren, report_ref, report_date, mention_type, url, note, provenance, license) values
  ('110000072', 'Préserver l''emploi : le ministère du travail face à la crise sanitaire', '2021-07-12', 'rapport', 'https://www.ccomptes.fr/fr/publications/preserver-lemploi-le-ministere-du-travail-face-la-crise-sanitaire', 'Réponse d''urgence du ministère du travail à la crise sanitaire : l''activité partielle a évité des destructions massives d''emplois, mais les contrôles ont été insuffisants et les coûts supérieurs aux prévisions.', 'cour_des_comptes', 'Licence Ouverte 2.0'),
  ('130005481', 'Pôle emploi à l''épreuve du chômage de masse', '2015-07-02', 'rapport', 'https://www.ccomptes.fr/fr/publications/pole-emploi-lepreuve-du-chomage-de-masse', 'Entre 2009 et 2015 les demandeurs d''emploi inscrits passent de 3,9 à 6,2 millions (+58 %) ; réorganisation engagée en 2012 mais difficultés opérationnelles persistantes face au chômage de masse.', 'cour_des_comptes', 'Licence Ouverte 2.0'),
  ('130005481', 'La gestion de Pôle emploi, dix ans après sa création', '2020-07-16', 'rapport', 'https://www.ccomptes.fr/fr/publications/la-gestion-de-pole-emploi-dix-ans-apres-sa-creation', 'Bilan dix ans après la fusion ANPE/Assédic : croissance continue des moyens, objectifs atteints mais peu ambitieux, interrogations sur certaines rémunérations dirigeantes.', 'cour_des_comptes', 'Licence Ouverte 2.0'),
  ('130005481', 'France Travail et l''intelligence artificielle', '2026-01-08', 'rapport', 'https://www.ccomptes.fr/fr/publications/france-travail-et-lintelligence-artificielle', 'Premier rapport de la Cour entièrement consacré à l''usage de l''IA par un grand opérateur de l''État : déploiement, effets et gouvernance, avec des points de vigilance (RGPD, encadrement éthique).', 'cour_des_comptes', 'Licence Ouverte 2.0'),
  ('180089013', 'Le CNRS et les sciences humaines et sociales', '2021-04-27', 'recommandation', 'https://www.ccomptes.fr/fr/publications/le-cnrs-et-les-sciences-humaines-et-sociales', 'Référé sur le pilotage des SHS via l''InSHS : progrès notés mais lacunes de coordination (alliance Athéna) et faiblesses d''infrastructures ; trois recommandations.', 'cour_des_comptes', 'Licence Ouverte 2.0'),
  ('180089013', 'Le Centre national de la recherche scientifique (CNRS)', '2025-03-25', 'rapport', 'https://www.ccomptes.fr/fr/publications/le-centre-national-de-la-recherche-scientifique-cnrs', 'Trésorerie pléthorique (~1,4 Md€ fin 2023) et sous-exécution budgétaire récurrente ; recrutements de chercheurs en baisse, gestion décentralisée des unités à renforcer.', 'cour_des_comptes', 'Licence Ouverte 2.0');


commit;
