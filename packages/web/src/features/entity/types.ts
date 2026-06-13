/** Curated `entities` row (subset the sheet reads). */
export interface EntityRow {
  siren: string;
  name: string;
  level: string;
  category: string | null;
  /** Tutelle (supervising ministry) SIREN; null for ministries / unresolved parents. */
  parent_siren: string | null;
  /** Registry source id that contributed this entity (mirrors edges). */
  provenance: string | null;
}

/**
 * Curated `budget_facts` row — a PLF/LFI figure at the mission/programme grain. Voted (`executed:
 * false`) vs executed (`true`); AE/CP are the commitment vs payment credits. The table carries no
 * `provenance` column, so budget rows render without a `ProvenanceBadge` (unlike edges).
 */
export interface BudgetFactRow {
  exercice: number;
  mission: string | null;
  programme: string | null;
  amount_ae_eur: number | null;
  amount_cp_eur: number | null;
  executed: boolean;
}

/** Curated `edges` row — a figure/relationship carrying its own provenance + millésime. */
export interface EdgeRow {
  source_siren: string;
  target_siren: string;
  type: string;
  amount_eur: number | null;
  exercice: number | null;
  provenance: string | null;
}

/** Curated `contracts` row (DECP) — a marché/concession the entity bought. */
export interface ContractRow {
  acheteur_siren: string | null;
  titulaire_siren: string | null;
  montant_eur: number | null;
  nature: string | null;
  exercice: number | null;
}

/** A linked entity resolved for readable labels + chip shapes (tutelle, counterparts, children). */
export interface RelatedEntity {
  siren: string;
  name: string;
  level: string | null;
  category: string | null;
}

/** Curated `attributions` row (FSC-27) — a legal mandate with a Légifrance reference. */
export interface AttributionRow {
  entity_siren: string;
  /** Human legal reference (e.g. the JORF décret number). */
  legal_ref: string | null;
  /** The competence / mandate text. */
  txt: string | null;
  /** Légifrance/JORF URL backing the legal_ref (validated http(s) before render). */
  source_url: string | null;
  /** Registry source id that contributed this row. */
  provenance: string | null;
}

/** Curated `mentions` row (FSC-62) — a Cour des comptes / CRTC oversight mention. */
export interface MentionRow {
  entity_siren: string;
  /** Report title / reference. */
  report_ref: string | null;
  /** ISO date string; formatted fr-FR at render. */
  report_date: string | null;
  /** "rapport" | "recommandation". */
  mention_type: string | null;
  /** Source report URL (validated http(s) before render). */
  url: string | null;
  /** Short note / excerpt. */
  note: string | null;
  /** Registry source id that contributed this row. */
  provenance: string | null;
  /** Per-row licence (the audit corpus is not uniformly licensed). */
  license: string | null;
}
