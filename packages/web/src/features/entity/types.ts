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
