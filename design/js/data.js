/* ============================================================================
   Example dataset — Cartographie des Fonds Publics
   Anchored on the real seed (3 ministères + CNRS, BnF, France Travail), then
   expanded into a plausible ~100-entity slice spanning the four administrative
   levels. ALL euro amounts are illustrative (« exemple ») unless tied to a
   published figure; provenance + millésime ride on every fact.
   ============================================================================ */
(function () {
  // ---- Level metadata (categorical, colour-blind-safe Okabe–Ito + shape cue) ----
  const LEVELS = {
    etat:    { id: "etat",    label: "État",    color: "#0072b2", bg: "#e3eef5", shape: "circle",   desc: "Administration centrale et opérateurs de l’État" },
    local:   { id: "local",   label: "Local",   color: "#009e73", bg: "#dcf0e9", shape: "square",   desc: "Collectivités territoriales" },
    social:  { id: "social",  label: "Social",  color: "#cc79a7", bg: "#f7e8f0", shape: "diamond",  desc: "Sécurité sociale" },
    delegue: { id: "delegue", label: "Délégué", color: "#e69f00", bg: "#fbeed4", shape: "triangle", desc: "Opérateurs délégués, titulaires de marchés" },
  };

  const SOURCES = [
    { id: "operateurs_etat", publisher: "Direction du budget — Jaune « Opérateurs de l’État »", licence: "Licence Ouverte 2.0", cadence: "Annuelle", millesime: "2025", updated: "2025-10-14", description: "Liste des opérateurs de l’État, tutelles et catégories (EPA, EPST, EPIC…)." },
    { id: "budget_plf_lfi", publisher: "budget.gouv.fr — PLF / LFI (PAP)", licence: "Licence Ouverte 2.0", cadence: "Annuelle", millesime: "2025", updated: "2025-10-10", description: "Crédits par mission et programme (AE/CP), voté et exécuté." },
    { id: "decp", publisher: "DAJ / Etalab — DECP consolidées", licence: "Licence Ouverte 2.0", cadence: "Mensuelle", millesime: "2026", updated: "2026-06-09", description: "Données essentielles de la commande publique : marchés et concessions." },
    { id: "sirene", publisher: "Insee — base SIRENE", licence: "Licence Ouverte 2.0", cadence: "Quotidienne", millesime: "2026", updated: "2026-06-08", description: "Répertoire des entreprises et établissements ; résolution des SIREN." },
    { id: "comptes_secu", publisher: "DSS — Comptes de la Sécurité sociale", licence: "Licence Ouverte 2.0", cadence: "Annuelle", millesime: "2024", updated: "2025-09-30", description: "Produits et charges des régimes de sécurité sociale." },
    { id: "ofgl", publisher: "OFGL — Observatoire des finances locales", licence: "Licence Ouverte 2.0", cadence: "Annuelle", millesime: "2024", updated: "2025-07-01", description: "Comptes des collectivités territoriales." },
  ];

  // ---- Entities ----------------------------------------------------------
  // helper to push entity
  const E = [];
  function ent(siren, name, level, category, parent, opts) {
    opts = opts || {};
    E.push({
      siren, name, level, category,
      parent_siren: parent || null,
      provenance: opts.prov || "operateurs_etat",
      cp_eur: opts.cp ?? null,           // CP magnitude (€), drives node size
      resolved: opts.resolved !== false, // false → « SIREN non résolu »
      acronym: opts.acr || null,
      mission: opts.mission || null,
    });
  }

  // ===== ÉTAT — ministères (graph roots) =====
  ent("110046018", "Ministère de la Culture", "etat", "ministère", null, { cp: 4200000000, acr: "MC" });
  ent("110044013", "Ministère de l’Enseignement supérieur et de la Recherche", "etat", "ministère", null, { cp: 31200000000, acr: "MESR" });
  ent("110000072", "Ministère du Travail et des Solidarités", "etat", "ministère", null, { cp: 22800000000, acr: "MTS" });

  // ----- Culture cluster -----
  ent("180046252", "Bibliothèque nationale de France", "etat", "EPA", "110046018", { cp: 254000000, acr: "BnF" });
  ent("180043016", "Musée du Louvre", "etat", "EPA", "110046018", { cp: 252000000 });
  ent("775670387", "Centre Pompidou", "etat", "EPA", "110046018", { cp: 124000000 });
  ent("180046443", "Château de Versailles", "etat", "EPA", "110046018", { cp: 116000000, acr: "EPV" });
  ent("784359069", "Opéra national de Paris", "etat", "EPIC", "110046018", { cp: 211000000 });
  ent("180046021", "Centre national du cinéma et de l’image animée", "etat", "EPA", "110046018", { cp: 712000000, acr: "CNC" });
  ent("301945269", "Institut national de l’audiovisuel", "etat", "EPIC", "110046018", { cp: 142000000, acr: "INA" });
  ent("180046096", "Centre des monuments nationaux", "etat", "EPA", "110046018", { cp: 168000000, acr: "CMN" });
  ent("130018299", "Mobilier national", "etat", "Service", "110046018", { cp: 28000000 });
  ent("775690703", "Cité de la musique — Philharmonie de Paris", "etat", "Association", "110046018", { cp: 39000000 });

  // ----- ESR cluster -----
  ent("180089013", "Centre national de la recherche scientifique", "etat", "EPST", "110044013", { cp: 3900000000, acr: "CNRS" });
  ent("180036048", "Institut national de la santé et de la recherche médicale", "etat", "EPST", "110044013", { cp: 998000000, acr: "Inserm" });
  ent("180070039", "Institut national de recherche pour l’agriculture, l’alimentation et l’environnement", "etat", "EPST", "110044013", { cp: 1020000000, acr: "INRAE" });
  ent("180089740", "Institut national de recherche en sciences et technologies du numérique", "etat", "EPST", "110044013", { cp: 178000000, acr: "Inria" });
  ent("775685019", "Commissariat à l’énergie atomique et aux énergies alternatives", "etat", "EPIC", "110044013", { cp: 4600000000, acr: "CEA" });
  ent("775665912", "Centre national d’études spatiales", "etat", "EPIC", "110044013", { cp: 2400000000, acr: "CNES" });
  ent("130015332", "Agence nationale de la recherche", "etat", "EPA", "110044013", { cp: 1100000000, acr: "ANR" });
  ent("197517177", "Université Paris-Saclay", "etat", "EPSCP", "110044013", { cp: 845000000 });
  ent("130031023", "Université PSL", "etat", "EPSCP", "110044013", { cp: 412000000 });
  ent("193100339", "Sorbonne Université", "etat", "EPSCP", "110044013", { cp: 668000000 });
  ent("775723876", "Centre national des œuvres universitaires et scolaires", "etat", "EPA", "110044013", { cp: 2700000000, acr: "Cnous" });
  ent("180020010", "Institut de recherche pour le développement", "etat", "EPST", "110044013", { cp: 232000000, acr: "IRD" });

  // ----- Travail cluster -----
  ent("130005481", "France Travail", "etat", "EPA", "110000072", { cp: 5800000000 });
  ent("824084658", "Agence nationale pour la formation professionnelle des adultes", "etat", "EPIC", "110000072", { cp: 730000000, acr: "Afpa" });
  ent("130025265", "France compétences", "etat", "EPA", "110000072", { cp: 9300000000 });
  ent("180092009", "Agence nationale pour l’amélioration des conditions de travail", "etat", "EPA", "110000072", { cp: 41000000, acr: "Anact" });
  ent("110068179", "Caisse nationale de l’assurance maladie — risque AT/MP", "etat", "Service", "110000072", { cp: 13000000000, resolved: false });

  // ===== SOCIAL — sécurité sociale =====
  ent("180035024", "Caisse nationale de l’assurance maladie", "social", "Caisse nationale", null, { cp: 245000000000, acr: "Cnam", prov: "comptes_secu" });
  ent("775678633", "Caisse nationale d’assurance vieillesse", "social", "Caisse nationale", null, { cp: 152000000000, acr: "Cnav", prov: "comptes_secu" });
  ent("180020075", "Caisse nationale des allocations familiales", "social", "Caisse nationale", null, { cp: 96000000000, acr: "Cnaf", prov: "comptes_secu" });
  ent("180035040", "Urssaf Caisse nationale", "social", "Caisse nationale", null, { cp: 580000000000, acr: "Acoss", prov: "comptes_secu" });
  ent("301846688", "Agirc-Arrco", "social", "Régime paritaire", null, { cp: 90000000000, prov: "comptes_secu" });
  ent("180090094", "Caisse centrale de la Mutualité sociale agricole", "social", "Régime", null, { cp: 28000000000, acr: "MSA", prov: "comptes_secu" });

  // ===== LOCAL — collectivités =====
  ent("237500139", "Région Île-de-France", "local", "Région", null, { cp: 5400000000, prov: "ofgl" });
  ent("200053781", "Métropole de Lyon", "local", "Métropole", null, { cp: 3700000000, prov: "ofgl" });
  ent("217500016", "Ville de Paris", "local", "Commune", null, { cp: 10600000000, prov: "ofgl" });
  ent("225900019", "Département du Nord", "local", "Département", null, { cp: 3900000000, prov: "ofgl" });
  ent("243300316", "Bordeaux Métropole", "local", "Métropole", null, { cp: 1850000000, prov: "ofgl" });
  ent("200054807", "Région Auvergne-Rhône-Alpes", "local", "Région", null, { cp: 3600000000, prov: "ofgl" });

  // ===== DÉLÉGUÉ — opérateurs délégués / titulaires de marchés =====
  ent("329200521", "Titulaire 329 200 521", "delegue", "Marché public", null, { cp: 1800000, resolved: false, prov: "decp" });
  ent("326556578", "Titulaire 326 556 578", "delegue", "Marché public", null, { cp: 85000, resolved: false, prov: "decp" });
  ent("552081317", "Groupe Demeter (BTP patrimoine)", "delegue", "Concession", null, { cp: 64000000, prov: "decp" });
  ent("402360441", "Société Helios Numérique", "delegue", "Marché public", null, { cp: 23000000, prov: "decp" });
  ent("552100554", "Société Restalia (restauration collective)", "delegue", "Délégation de service public", null, { cp: 47000000, prov: "decp" });
  ent("440048882", "Atlas Édition scientifique", "delegue", "Marché public", null, { cp: 12500000, prov: "decp" });
  ent("552032534", "EnerGaïa Énergies", "delegue", "Concession", null, { cp: 88000000, prov: "decp" });

  // generated mid-tier operators to thicken clusters (clearly fictional)
  const FILL = [
    ["110046018", "Réunion des musées nationaux — Grand Palais", "EPIC", 188000000],
    ["110046018", "Institut national d’histoire de l’art", "EPA", 14000000],
    ["110046018", "Cité de l’architecture et du patrimoine", "EPIC", 31000000],
    ["110046018", "Centre national des arts plastiques", "EPA", 24000000],
    ["110046018", "Musée d’Orsay et de l’Orangerie", "EPA", 96000000],
    ["110046018", "Musée du quai Branly — Jacques Chirac", "EPA", 72000000],
    ["110046018", "Comédie-Française", "EPIC", 41000000],
    ["110044013", "École nationale supérieure des Mines", "EPSCP", 118000000],
    ["110044013", "Institut Polytechnique de Paris", "EPSCP", 380000000],
    ["110044013", "Université Grenoble-Alpes", "EPSCP", 590000000],
    ["110044013", "Université de Strasbourg", "EPSCP", 520000000],
    ["110044013", "Université d’Aix-Marseille", "EPSCP", 760000000],
    ["110044013", "Conservatoire national des arts et métiers", "EPSCP", 122000000],
    ["110044013", "Institut national d’études démographiques", "EPST", 19000000],
    ["110044013", "Office national d’études aérospatiales", "EPIC", 290000000],
    ["110044013", "Bureau de recherches géologiques et minières", "EPIC", 142000000],
    ["110044013", "Institut français de recherche pour l’exploitation de la mer", "EPIC", 215000000],
    ["110000072", "Agence nationale de santé publique", "EPA", 195000000],
    ["110000072", "Institut national du travail, de l’emploi et de la formation professionnelle", "EPA", 16000000],
    ["110000072", "Caisse des dépôts — gestion de France 2030", "Service", 0, false],
  ];
  let gen = 400000001;
  FILL.forEach(([parent, name, cat, cp, resolved]) => {
    ent(String(gen++), name, "etat", cat, parent, { cp: cp || null, resolved: resolved !== false });
  });

  // ---- Edges -------------------------------------------------------------
  const X = [];
  function edge(s, t, type, amount, exercice, prov) {
    X.push({ source_siren: s, target_siren: t, type, amount_eur: amount ?? null, exercice: exercice ?? null, provenance: prov || "operateurs_etat" });
  }
  // tutelle: ministry -> every operator that has it as parent
  E.forEach((e) => {
    if (e.parent_siren && e.level === "etat") edge(e.parent_siren, e.siren, "tutelle", null, null, "operateurs_etat");
  });
  // also AT/MP service link
  // funds: ministry -> operator (subvention pour charges de service public, exemple)
  edge("110046018", "180046252", "funds", 198000000, 2025, "budget_plf_lfi");
  edge("110046018", "180043016", "funds", 99000000, 2025, "budget_plf_lfi");
  edge("110046018", "180046021", "funds", 712000000, 2025, "budget_plf_lfi");
  edge("110046018", "784359069", "funds", 95000000, 2025, "budget_plf_lfi");
  edge("110046018", "180046096", "funds", 102000000, 2025, "budget_plf_lfi");
  edge("110044013", "180089013", "funds", 2950000000, 2025, "budget_plf_lfi");
  edge("110044013", "180036048", "funds", 720000000, 2025, "budget_plf_lfi");
  edge("110044013", "775685019", "funds", 1750000000, 2025, "budget_plf_lfi");
  edge("110044013", "775665912", "funds", 2100000000, 2025, "budget_plf_lfi");
  edge("110044013", "130015332", "funds", 1100000000, 2025, "budget_plf_lfi");
  edge("110044013", "775723876", "funds", 2700000000, 2025, "budget_plf_lfi");
  edge("110044013", "180070039", "funds", 690000000, 2025, "budget_plf_lfi");
  edge("110000072", "130005481", "funds", 1350000000, 2025, "budget_plf_lfi");
  edge("110000072", "824084658", "funds", 110000000, 2025, "budget_plf_lfi");
  edge("110000072", "130025265", "funds", 1600000000, 2025, "budget_plf_lfi");

  // participation / cofinancement: collectivités & social -> operators
  edge("237500139", "193100339", "funds", 64000000, 2024, "ofgl");
  edge("237500139", "197517177", "funds", 88000000, 2024, "ofgl");
  edge("200053781", "130031023", "funds", 12000000, 2024, "ofgl");
  edge("217500016", "775670387", "funds", 9000000, 2024, "ofgl");
  edge("217500016", "784359069", "funds", 7000000, 2024, "ofgl");
  edge("180035024", "180036048", "participation", 240000000, 2024, "comptes_secu");
  edge("301846688", "130005481", "participation", 4000000000, 2024, "comptes_secu");

  // delegates (dashed): operator -> titulaire (marché / DSP)
  edge("180089013", "329200521", "delegates", 1800000, 2026, "decp");
  edge("180089013", "326556578", "delegates", 85000, 2026, "decp");
  edge("180046252", "440048882", "delegates", 4200000, 2026, "decp");
  edge("180043016", "552081317", "delegates", 48000000, 2026, "decp");
  edge("784359069", "552100554", "delegates", 22000000, 2026, "decp");
  edge("775685019", "552032534", "delegates", 64000000, 2026, "decp");
  edge("130005481", "402360441", "delegates", 19000000, 2026, "decp");
  edge("180046096", "552081317", "delegates", 16000000, 2026, "decp");

  // ---- Budget facts (PLF 2025, mission/programme grain) ------------------
  const BUDGET = [
    // MESR — MIRES (real PLF 2025 voté figures from the seed)
    { entity_siren: "110044013", exercice: 2025, mission: "MIRES", programme: "150 — Formations supérieures et recherche universitaire", amount_ae_eur: 15217000000, amount_cp_eur: 15279000000, executed: false, provenance: "budget_plf_lfi" },
    { entity_siren: "110044013", exercice: 2025, mission: "MIRES", programme: "172 — Recherches scientifiques et technologiques pluridisciplinaires", amount_ae_eur: 8259807441, amount_cp_eur: 8701105312, executed: false, provenance: "budget_plf_lfi" },
    { entity_siren: "110044013", exercice: 2025, mission: "MIRES", programme: "193 — Recherche spatiale", amount_ae_eur: 2100000000, amount_cp_eur: 2100000000, executed: false, provenance: "budget_plf_lfi" },
    { entity_siren: "110044013", exercice: 2024, mission: "MIRES", programme: "150 — Formations supérieures et recherche universitaire", amount_ae_eur: 14690000000, amount_cp_eur: 14710000000, executed: true, provenance: "budget_plf_lfi" },
    { entity_siren: "110044013", exercice: 2024, mission: "MIRES", programme: "172 — Recherches scientifiques et technologiques pluridisciplinaires", amount_ae_eur: 7980000000, amount_cp_eur: 8120000000, executed: true, provenance: "budget_plf_lfi" },
    // Culture — mission Culture + Médias
    { entity_siren: "110046018", exercice: 2025, mission: "Culture", programme: "175 — Patrimoines", amount_ae_eur: 1240000000, amount_cp_eur: 1190000000, executed: false, provenance: "budget_plf_lfi" },
    { entity_siren: "110046018", exercice: 2025, mission: "Culture", programme: "131 — Création", amount_ae_eur: 1010000000, amount_cp_eur: 990000000, executed: false, provenance: "budget_plf_lfi" },
    { entity_siren: "110046018", exercice: 2025, mission: "Culture", programme: "224 — Soutien aux politiques culturelles", amount_ae_eur: 780000000, amount_cp_eur: 760000000, executed: false, provenance: "budget_plf_lfi" },
    // Travail — mission Travail et emploi
    { entity_siren: "110000072", exercice: 2025, mission: "Travail et emploi", programme: "102 — Accès et retour à l’emploi", amount_ae_eur: 7100000000, amount_cp_eur: 6980000000, executed: false, provenance: "budget_plf_lfi" },
    { entity_siren: "110000072", exercice: 2025, mission: "Travail et emploi", programme: "103 — Accompagnement des mutations économiques", amount_ae_eur: 8800000000, amount_cp_eur: 8400000000, executed: false, provenance: "budget_plf_lfi" },
  ];

  // ---- Contracts (DECP) ---------------------------------------------------
  const CONTRACTS = [
    { acheteur_siren: "180089013", titulaire_siren: "329200521", montant_eur: 1800000, nature: "marche", exercice: 2026, objet: "Instruments scientifiques — spectrométrie" },
    { acheteur_siren: "180089013", titulaire_siren: "326556578", montant_eur: 84925.39, nature: "marche", exercice: 2026, objet: "Maintenance d’équipements de laboratoire" },
    { acheteur_siren: "180043016", titulaire_siren: "552081317", montant_eur: 48000000, nature: "marche", exercice: 2026, objet: "Restauration du patrimoine bâti — aile Richelieu" },
    { acheteur_siren: "784359069", titulaire_siren: "552100554", montant_eur: 22000000, nature: "concession", exercice: 2026, objet: "Restauration collective et accueil" },
    { acheteur_siren: "775685019", titulaire_siren: "552032534", montant_eur: 64000000, nature: "concession", exercice: 2026, objet: "Fourniture et exploitation énergétique" },
    { acheteur_siren: "180046252", titulaire_siren: "440048882", montant_eur: 4200000, nature: "marche", exercice: 2026, objet: "Numérisation et édition de fonds patrimoniaux" },
  ];

  window.DATA = { LEVELS, SOURCES, entities: E, edges: X, budgetFacts: BUDGET, contracts: CONTRACTS };
})();
