-- supabase/demo_seed.sql — ILLUSTRATIVE demo seed (FSC-50…53). GENERATED, do not edit by hand:
-- regenerate with `make demo-seed` (source: packages/ingestion/src/ingestion/demo_seed.py).
--
-- A design-scale, plausible État-central + local + social + délégué slice so the redesigned
-- screens render rich graphs, flows and figures in local dev / Vercel previews before the
-- funding-flow ingestion (FSC-39/FSC-33) lands. DEV/PREVIEW ONLY — never apply to production.
--
-- Euro amounts are ILLUSTRATIVE (« exemple ») unless published: the MESR/MIRES budget rows are the
-- real PLF 2025 voté totals. Two DECP titulaires are referenced by edges/contracts with no entity
-- row, so the UI shows them as « SIREN non résolu ». Licence Ouverte / Etalab 2.0 where attributed.
--
-- The attributions (« mandat légal ») + mentions (« épinglé par la Cour ») rows are ILLUSTRATIVE,
-- clearly « Exemple », so the « why »/oversight fiche sections + the graph badge render here too
-- (FSC-71). The real, verifiable oversight/why rows live in the curated seed (`make seed`).


begin;

-- Idempotent: clear the curated tables, then re-insert the illustrative slice.
truncate entities, edges, budget_facts, contracts, attributions, mentions restart identity cascade;

-- Entities (illustrative operators across the four levels).
insert into entities (siren, name, level, category, parent_siren, provenance) values
  ('402360441', 'Société Helios Numérique', 'delegated', 'Marché public', null, 'decp_commande_publique'),
  ('440048882', 'Atlas Édition scientifique', 'delegated', 'Marché public', null, 'decp_commande_publique'),
  ('529000019', 'SPL Paris Seine Ouest Aménagement', 'delegated', 'SPL', null, 'epl_sem_spl'),
  ('552032534', 'EnerGaïa Énergies', 'delegated', 'Concession', null, 'decp_commande_publique'),
  ('552032708', 'SEM Lyon Confluence', 'delegated', 'SEM', null, 'epl_sem_spl'),
  ('552081317', 'Groupe Demeter (BTP patrimoine)', 'delegated', 'Concession', null, 'decp_commande_publique'),
  ('552100554', 'Société Restalia (restauration collective)', 'delegated', 'Délégation de service public', null, 'decp_commande_publique'),
  ('200053781', 'Métropole de Lyon', 'local', 'Métropole', null, 'finances_locales_ofgl'),
  ('200054807', 'Région Auvergne-Rhône-Alpes', 'local', 'Région', null, 'finances_locales_ofgl'),
  ('217500016', 'Ville de Paris', 'local', 'Commune', null, 'finances_locales_ofgl'),
  ('225900019', 'Département du Nord', 'local', 'Département', null, 'finances_locales_ofgl'),
  ('237500139', 'Région Île-de-France', 'local', 'Région', null, 'finances_locales_ofgl'),
  ('243300316', 'Bordeaux Métropole', 'local', 'Métropole', null, 'finances_locales_ofgl'),
  ('180020075', 'Caisse nationale des allocations familiales', 'social', 'Caisse nationale', null, 'comptes_sociaux'),
  ('180035024', 'Caisse nationale de l’assurance maladie', 'social', 'Caisse nationale', null, 'comptes_sociaux'),
  ('180035040', 'Urssaf Caisse nationale', 'social', 'Caisse nationale', null, 'comptes_sociaux'),
  ('180090094', 'Caisse centrale de la Mutualité sociale agricole', 'social', 'Régime', null, 'comptes_sociaux'),
  ('301846688', 'Agirc-Arrco', 'social', 'Régime paritaire', null, 'comptes_sociaux'),
  ('775678633', 'Caisse nationale d’assurance vieillesse', 'social', 'Caisse nationale', null, 'comptes_sociaux'),
  ('110000072', 'Ministère du Travail et des Solidarités', 'state', 'ministère', null, 'operateurs_etat'),
  ('110044013', 'Ministère de l’Enseignement supérieur et de la Recherche', 'state', 'ministère', null, 'operateurs_etat'),
  ('110046018', 'Ministère de la Culture', 'state', 'ministère', null, 'operateurs_etat'),
  ('130005481', 'France Travail', 'state', 'EPA', '110000072', 'operateurs_etat'),
  ('130015332', 'Agence nationale de la recherche', 'state', 'EPA', '110044013', 'operateurs_etat'),
  ('130018299', 'Mobilier national', 'state', 'Service', '110046018', 'operateurs_etat'),
  ('130025265', 'France compétences', 'state', 'EPA', '110000072', 'operateurs_etat'),
  ('130031023', 'Université PSL', 'state', 'EPSCP', '110044013', 'operateurs_etat'),
  ('180020010', 'Institut de recherche pour le développement', 'state', 'EPST', '110044013', 'operateurs_etat'),
  ('180036048', 'Institut national de la santé et de la recherche médicale', 'state', 'EPST', '110044013', 'operateurs_etat'),
  ('180043016', 'Musée du Louvre', 'state', 'EPA', '110046018', 'operateurs_etat'),
  ('180046021', 'Centre national du cinéma et de l’image animée', 'state', 'EPA', '110046018', 'operateurs_etat'),
  ('180046096', 'Centre des monuments nationaux', 'state', 'EPA', '110046018', 'operateurs_etat'),
  ('180046252', 'Bibliothèque nationale de France', 'state', 'EPA', '110046018', 'operateurs_etat'),
  ('180046443', 'Château de Versailles', 'state', 'EPA', '110046018', 'operateurs_etat'),
  ('180070039', 'Institut national de recherche pour l’agriculture, l’alimentation et l’environnement', 'state', 'EPST', '110044013', 'operateurs_etat'),
  ('180089013', 'Centre national de la recherche scientifique', 'state', 'EPST', '110044013', 'operateurs_etat'),
  ('180089740', 'Institut national de recherche en sciences et technologies du numérique', 'state', 'EPST', '110044013', 'operateurs_etat'),
  ('180092009', 'Agence nationale pour l’amélioration des conditions de travail', 'state', 'EPA', '110000072', 'operateurs_etat'),
  ('193100339', 'Sorbonne Université', 'state', 'EPSCP', '110044013', 'operateurs_etat'),
  ('197517177', 'Université Paris-Saclay', 'state', 'EPSCP', '110044013', 'operateurs_etat'),
  ('301945269', 'Institut national de l’audiovisuel', 'state', 'EPIC', '110046018', 'operateurs_etat'),
  ('400000001', 'Réunion des musées nationaux — Grand Palais', 'state', 'EPIC', '110046018', 'operateurs_etat'),
  ('400000002', 'Institut national d’histoire de l’art', 'state', 'EPA', '110046018', 'operateurs_etat'),
  ('400000003', 'Cité de l’architecture et du patrimoine', 'state', 'EPIC', '110046018', 'operateurs_etat'),
  ('400000004', 'Centre national des arts plastiques', 'state', 'EPA', '110046018', 'operateurs_etat'),
  ('400000005', 'Musée d’Orsay et de l’Orangerie', 'state', 'EPA', '110046018', 'operateurs_etat'),
  ('400000006', 'Musée du quai Branly — Jacques Chirac', 'state', 'EPA', '110046018', 'operateurs_etat'),
  ('400000007', 'Comédie-Française', 'state', 'EPIC', '110046018', 'operateurs_etat'),
  ('400000008', 'École nationale supérieure des Mines', 'state', 'EPSCP', '110044013', 'operateurs_etat'),
  ('400000009', 'Institut Polytechnique de Paris', 'state', 'EPSCP', '110044013', 'operateurs_etat'),
  ('400000010', 'Université Grenoble-Alpes', 'state', 'EPSCP', '110044013', 'operateurs_etat'),
  ('400000011', 'Université de Strasbourg', 'state', 'EPSCP', '110044013', 'operateurs_etat'),
  ('400000012', 'Université d’Aix-Marseille', 'state', 'EPSCP', '110044013', 'operateurs_etat'),
  ('400000013', 'Conservatoire national des arts et métiers', 'state', 'EPSCP', '110044013', 'operateurs_etat'),
  ('400000014', 'Institut national d’études démographiques', 'state', 'EPST', '110044013', 'operateurs_etat'),
  ('400000015', 'Office national d’études aérospatiales', 'state', 'EPIC', '110044013', 'operateurs_etat'),
  ('400000016', 'Bureau de recherches géologiques et minières', 'state', 'EPIC', '110044013', 'operateurs_etat'),
  ('400000017', 'Institut français de recherche pour l’exploitation de la mer', 'state', 'EPIC', '110044013', 'operateurs_etat'),
  ('400000018', 'Agence nationale de santé publique', 'state', 'EPA', '110000072', 'operateurs_etat'),
  ('400000019', 'Institut national du travail, de l’emploi et de la formation professionnelle', 'state', 'EPA', '110000072', 'operateurs_etat'),
  ('775665912', 'Centre national d’études spatiales', 'state', 'EPIC', '110044013', 'operateurs_etat'),
  ('775670387', 'Centre Pompidou', 'state', 'EPA', '110046018', 'operateurs_etat'),
  ('775685019', 'Commissariat à l’énergie atomique et aux énergies alternatives', 'state', 'EPIC', '110044013', 'operateurs_etat'),
  ('775690703', 'Cité de la musique — Philharmonie de Paris', 'state', 'Association', '110046018', 'operateurs_etat'),
  ('775723876', 'Centre national des œuvres universitaires et scolaires', 'state', 'EPA', '110044013', 'operateurs_etat'),
  ('784359069', 'Opéra national de Paris', 'state', 'EPIC', '110046018', 'operateurs_etat'),
  ('824084658', 'Agence nationale pour la formation professionnelle des adultes', 'state', 'EPIC', '110000072', 'operateurs_etat');

-- Edges: tutelle + illustrative funds / participation / delegates flows.
insert into edges (source_siren, target_siren, type, amount_eur, exercice, provenance) values
  ('110000072', '130005481', 'funds', 1350000000, 2025, 'budget_plf_lfi'),
  ('110000072', '130005481', 'tutelle', null, null, 'operateurs_etat'),
  ('110000072', '130025265', 'funds', 1600000000, 2025, 'budget_plf_lfi'),
  ('110000072', '130025265', 'tutelle', null, null, 'operateurs_etat'),
  ('110000072', '180092009', 'tutelle', null, null, 'operateurs_etat'),
  ('110000072', '400000018', 'tutelle', null, null, 'operateurs_etat'),
  ('110000072', '400000019', 'tutelle', null, null, 'operateurs_etat'),
  ('110000072', '824084658', 'funds', 110000000, 2025, 'budget_plf_lfi'),
  ('110000072', '824084658', 'tutelle', null, null, 'operateurs_etat'),
  ('110044013', '130015332', 'funds', 1100000000, 2025, 'budget_plf_lfi'),
  ('110044013', '130015332', 'tutelle', null, null, 'operateurs_etat'),
  ('110044013', '130031023', 'tutelle', null, null, 'operateurs_etat'),
  ('110044013', '180020010', 'tutelle', null, null, 'operateurs_etat'),
  ('110044013', '180036048', 'funds', 720000000, 2025, 'budget_plf_lfi'),
  ('110044013', '180036048', 'tutelle', null, null, 'operateurs_etat'),
  ('110044013', '180070039', 'funds', 690000000, 2025, 'budget_plf_lfi'),
  ('110044013', '180070039', 'tutelle', null, null, 'operateurs_etat'),
  ('110044013', '180089013', 'funds', 2950000000, 2025, 'budget_plf_lfi'),
  ('110044013', '180089013', 'tutelle', null, null, 'operateurs_etat'),
  ('110044013', '180089740', 'tutelle', null, null, 'operateurs_etat'),
  ('110044013', '193100339', 'tutelle', null, null, 'operateurs_etat'),
  ('110044013', '197517177', 'tutelle', null, null, 'operateurs_etat'),
  ('110044013', '400000008', 'tutelle', null, null, 'operateurs_etat'),
  ('110044013', '400000009', 'tutelle', null, null, 'operateurs_etat'),
  ('110044013', '400000010', 'tutelle', null, null, 'operateurs_etat'),
  ('110044013', '400000011', 'tutelle', null, null, 'operateurs_etat'),
  ('110044013', '400000012', 'tutelle', null, null, 'operateurs_etat'),
  ('110044013', '400000013', 'tutelle', null, null, 'operateurs_etat'),
  ('110044013', '400000014', 'tutelle', null, null, 'operateurs_etat'),
  ('110044013', '400000015', 'tutelle', null, null, 'operateurs_etat'),
  ('110044013', '400000016', 'tutelle', null, null, 'operateurs_etat'),
  ('110044013', '400000017', 'tutelle', null, null, 'operateurs_etat'),
  ('110044013', '775665912', 'funds', 2100000000, 2025, 'budget_plf_lfi'),
  ('110044013', '775665912', 'tutelle', null, null, 'operateurs_etat'),
  ('110044013', '775685019', 'funds', 1750000000, 2025, 'budget_plf_lfi'),
  ('110044013', '775685019', 'tutelle', null, null, 'operateurs_etat'),
  ('110044013', '775723876', 'funds', 2700000000, 2025, 'budget_plf_lfi'),
  ('110044013', '775723876', 'tutelle', null, null, 'operateurs_etat'),
  ('110046018', '130018299', 'tutelle', null, null, 'operateurs_etat'),
  ('110046018', '180043016', 'funds', 99000000, 2025, 'budget_plf_lfi'),
  ('110046018', '180043016', 'tutelle', null, null, 'operateurs_etat'),
  ('110046018', '180046021', 'funds', 712000000, 2025, 'budget_plf_lfi'),
  ('110046018', '180046021', 'tutelle', null, null, 'operateurs_etat'),
  ('110046018', '180046096', 'funds', 102000000, 2025, 'budget_plf_lfi'),
  ('110046018', '180046096', 'tutelle', null, null, 'operateurs_etat'),
  ('110046018', '180046252', 'funds', 198000000, 2025, 'budget_plf_lfi'),
  ('110046018', '180046252', 'tutelle', null, null, 'operateurs_etat'),
  ('110046018', '180046443', 'tutelle', null, null, 'operateurs_etat'),
  ('110046018', '301945269', 'tutelle', null, null, 'operateurs_etat'),
  ('110046018', '400000001', 'tutelle', null, null, 'operateurs_etat'),
  ('110046018', '400000002', 'tutelle', null, null, 'operateurs_etat'),
  ('110046018', '400000003', 'tutelle', null, null, 'operateurs_etat'),
  ('110046018', '400000004', 'tutelle', null, null, 'operateurs_etat'),
  ('110046018', '400000005', 'tutelle', null, null, 'operateurs_etat'),
  ('110046018', '400000006', 'tutelle', null, null, 'operateurs_etat'),
  ('110046018', '400000007', 'tutelle', null, null, 'operateurs_etat'),
  ('110046018', '775670387', 'tutelle', null, null, 'operateurs_etat'),
  ('110046018', '775690703', 'tutelle', null, null, 'operateurs_etat'),
  ('110046018', '784359069', 'funds', 95000000, 2025, 'budget_plf_lfi'),
  ('110046018', '784359069', 'tutelle', null, null, 'operateurs_etat'),
  ('130005481', '402360441', 'delegates', 19000000, 2026, 'decp_commande_publique'),
  ('180035024', '180036048', 'participation', 240000000, 2024, 'comptes_sociaux'),
  ('180043016', '552081317', 'delegates', 48000000, 2026, 'decp_commande_publique'),
  ('180046096', '552081317', 'delegates', 16000000, 2026, 'decp_commande_publique'),
  ('180046252', '440048882', 'delegates', 4200000, 2026, 'decp_commande_publique'),
  ('180089013', '326556578', 'delegates', 85000, 2026, 'decp_commande_publique'),
  ('180089013', '329200521', 'delegates', 1800000, 2026, 'decp_commande_publique'),
  ('200053781', '130031023', 'funds', 12000000, 2024, 'finances_locales_ofgl'),
  ('200053781', '552032708', 'participation', null, null, 'epl_sem_spl'),
  ('217500016', '529000019', 'participation', null, null, 'epl_sem_spl'),
  ('217500016', '775670387', 'funds', 9000000, 2024, 'finances_locales_ofgl'),
  ('217500016', '784359069', 'funds', 7000000, 2024, 'finances_locales_ofgl'),
  ('237500139', '193100339', 'funds', 64000000, 2024, 'finances_locales_ofgl'),
  ('237500139', '197517177', 'funds', 88000000, 2024, 'finances_locales_ofgl'),
  ('301846688', '130005481', 'participation', 4000000000, 2024, 'comptes_sociaux'),
  ('775685019', '552032534', 'delegates', 64000000, 2026, 'decp_commande_publique'),
  ('784359069', '552100554', 'delegates', 22000000, 2026, 'decp_commande_publique');

-- Budget facts: MESR/MIRES real PLF totals + illustrative missions/years.
insert into budget_facts (entity_siren, exercice, mission, programme, amount_ae_eur, amount_cp_eur, executed, nomenclature, provenance) values
  ('110044013', 2025, 'MIRES', '150 — Formations supérieures et recherche universitaire', 15217000000, 15279000000, false, 'lolf', 'budget_plf_lfi'),
  ('110044013', 2025, 'MIRES', '172 — Recherches scientifiques et technologiques pluridisciplinaires', 8259807441, 8701105312, false, 'lolf', 'budget_plf_lfi'),
  ('110044013', 2025, 'MIRES', '193 — Recherche spatiale', 2100000000, 2100000000, false, 'lolf', 'budget_plf_lfi'),
  ('110044013', 2024, 'MIRES', '150 — Formations supérieures et recherche universitaire', 14690000000, 14710000000, true, 'lolf', 'budget_plf_lfi'),
  ('110044013', 2024, 'MIRES', '172 — Recherches scientifiques et technologiques pluridisciplinaires', 7980000000, 8120000000, true, 'lolf', 'budget_plf_lfi'),
  ('110046018', 2025, 'Culture', '175 — Patrimoines', 1240000000, 1190000000, false, 'lolf', 'budget_plf_lfi'),
  ('110046018', 2025, 'Culture', '131 — Création', 1010000000, 990000000, false, 'lolf', 'budget_plf_lfi'),
  ('110046018', 2025, 'Culture', '224 — Soutien aux politiques culturelles', 780000000, 760000000, false, 'lolf', 'budget_plf_lfi'),
  ('110000072', 2025, 'Travail et emploi', '102 — Accès et retour à l’emploi', 7100000000, 6980000000, false, 'lolf', 'budget_plf_lfi'),
  ('110000072', 2025, 'Travail et emploi', '103 — Accompagnement des mutations économiques', 8800000000, 8400000000, false, 'lolf', 'budget_plf_lfi'),
  ('237500139', 2023, null, 'Dépenses de fonctionnement', null, 3400000000, true, 'm57', 'finances_locales_ofgl'),
  ('237500139', 2023, null, 'Dépenses d’investissement', null, 2100000000, true, 'm57', 'finances_locales_ofgl'),
  ('200053781', 2023, null, 'Dépenses de fonctionnement', null, 2300000000, true, 'm57', 'finances_locales_ofgl'),
  ('200053781', 2023, null, 'Dépenses d’investissement', null, 900000000, true, 'm57', 'finances_locales_ofgl'),
  ('217500016', 2023, null, 'Dépenses de fonctionnement', null, 8000000000, true, 'm57', 'finances_locales_ofgl'),
  ('217500016', 2023, null, 'Dépenses d’investissement', null, 1500000000, true, 'm57', 'finances_locales_ofgl'),
  ('180035024', 2023, null, 'Maladie', null, 245000000000, true, 'social', 'comptes_sociaux'),
  ('775678633', 2023, null, 'Vieillesse', null, 275000000000, true, 'social', 'comptes_sociaux'),
  ('180020075', 2023, null, 'Famille', null, 56000000000, true, 'social', 'comptes_sociaux');

-- Contracts (illustrative DECP marchés / concessions).
insert into contracts (acheteur_siren, titulaire_siren, montant_eur, nature, exercice, provenance) values
  ('180089013', '329200521', 1800000, 'marche', 2026, 'decp_commande_publique'),
  ('180089013', '326556578', 84925.39, 'marche', 2026, 'decp_commande_publique'),
  ('180043016', '552081317', 48000000, 'marche', 2026, 'decp_commande_publique'),
  ('784359069', '552100554', 22000000, 'concession', 2026, 'decp_commande_publique'),
  ('775685019', '552032534', 64000000, 'concession', 2026, 'decp_commande_publique'),
  ('180046252', '440048882', 4200000, 'marche', 2026, 'decp_commande_publique');

-- Attributions: illustrative « mandat légal » on the demo ministries (« Exemple »).
insert into attributions (entity_siren, legal_ref, txt, source_url, provenance) values
  ('110000072', 'Exemple — décret d''attribution (jeu de démonstration)', 'Exemple illustratif (fictif) : mandat légal de démonstration (travail, emploi et solidarités). Données réelles via `make seed`.', 'https://www.legifrance.gouv.fr', 'legifrance_attributions'),
  ('110044013', 'Exemple — décret d''attribution (jeu de démonstration)', 'Exemple illustratif (fictif) : mandat légal de démonstration (enseignement supérieur, recherche et espace). Données réelles via `make seed`.', 'https://www.legifrance.gouv.fr', 'legifrance_attributions'),
  ('110046018', 'Exemple — décret d''attribution (jeu de démonstration)', 'Exemple illustratif (fictif) : mandat légal de démonstration montrant la section « Attributions / mandat légal » (politique du patrimoine, de la création et de l''accès à la culture). Les attributions réelles sont chargées par `make seed`.', 'https://www.legifrance.gouv.fr', 'legifrance_attributions');

-- Mentions: illustrative « épinglé par la Cour » oversight signals (« Exemple »).
insert into mentions (entity_siren, report_ref, report_date, mention_type, url, note, provenance, license) values
  ('110000072', 'Exemple — recommandation (jeu de démonstration)', '2025-01-30', 'recommandation', 'https://www.ccomptes.fr/fr/publications', 'Exemple illustratif (fictif) : recommandation de démonstration. Données réelles via `make seed`.', 'cour_des_comptes', 'Licence Ouverte 2.0'),
  ('130005481', 'Exemple — recommandation (jeu de démonstration)', '2024-07-16', 'recommandation', 'https://www.ccomptes.fr/fr/publications', 'Exemple illustratif (fictif) : recommandation de démonstration. Données réelles via `make seed`.', 'cour_des_comptes', 'Licence Ouverte 2.0'),
  ('180043016', 'Exemple — rapport (jeu de démonstration)', '2024-11-04', 'rapport', 'https://www.ccomptes.fr/fr/publications', 'Exemple illustratif (fictif) : rapport de démonstration. Données réelles via `make seed`.', 'cour_des_comptes', 'Licence Ouverte 2.0'),
  ('180089013', 'Exemple — rapport thématique (jeu de démonstration)', '2025-03-25', 'rapport', 'https://www.ccomptes.fr/fr/publications', 'Exemple illustratif (fictif) : cette mention « épinglé par la Cour » illustre la section « Contrôle / Cour des comptes » et le badge du graphe. Les mentions réelles via `make seed`.', 'cour_des_comptes', 'Licence Ouverte 2.0'),
  ('197517177', 'Exemple — rapport (jeu de démonstration)', '2023-09-14', 'rapport', 'https://www.ccomptes.fr/fr/publications', 'Exemple illustratif (fictif) : rapport de démonstration. Données réelles via `make seed`.', 'cour_des_comptes', 'Licence Ouverte 2.0'),
  ('237500139', 'Exemple — rapport de chambre régionale (jeu de démonstration)', '2024-05-20', 'rapport', 'https://www.ccomptes.fr/fr/publications', 'Exemple illustratif (fictif) : observations de démonstration (type CRC/CRTC). Données réelles via `make seed`.', 'cour_des_comptes', 'Licence Ouverte 2.0');


commit;
