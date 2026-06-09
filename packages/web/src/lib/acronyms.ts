/**
 * Display acronyms for the institutions that have a well-known short form — used in breadcrumbs,
 * search results and the Sankey labels. The curated `entities` table has no `acronym` column, so
 * this is a small client-side map keyed by SIREN (mirrors the design reference's `acr` values).
 * Falls back to the full name when there is no acronym.
 */
const ACRONYM_BY_SIREN: Record<string, string> = {
  "110046018": "MC", // Ministère de la Culture
  "110044013": "MESR", // Enseignement supérieur et Recherche
  "110000072": "MTS", // Travail et Solidarités
  "180046252": "BnF",
  "180046443": "EPV", // Château de Versailles
  "180046021": "CNC",
  "301945269": "INA",
  "180046096": "CMN",
  "180089013": "CNRS",
  "180036048": "Inserm",
  "180070039": "INRAE",
  "180089740": "Inria",
  "775685019": "CEA",
  "775665912": "CNES",
  "130015332": "ANR",
  "775723876": "Cnous",
  "180020010": "IRD",
  "824084658": "Afpa",
  "180092009": "Anact",
  "180035024": "Cnam",
  "775678633": "Cnav",
  "180020075": "Cnaf",
  "180035040": "Acoss",
  "180090094": "MSA",
};

/** The acronym for a SIREN, or `null` if none is known. */
export function acronymOf(siren: string | null | undefined): string | null {
  return siren ? (ACRONYM_BY_SIREN[siren] ?? null) : null;
}

/** A short label for an entity: its acronym if known, else the full name. */
export function shortLabel(siren: string | null | undefined, name: string): string {
  return acronymOf(siren) ?? name;
}
