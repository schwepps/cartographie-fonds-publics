/** Curated `entities` row (subset the sheet reads). */
export interface EntityRow {
  siren: string;
  name: string;
  level: string;
  category: string | null;
  /** Registry source id that contributed this entity (mirrors edges). */
  provenance: string | null;
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
