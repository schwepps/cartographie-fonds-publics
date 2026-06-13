/**
 * Administrative-level metadata — the single source of truth for the data-viz palette, the
 * non-colour shape cue and the human label per level. Keyed by the curated `entities.level` value
 * (DB constraint in `supabase/migrations/0001_init.sql`: `state | local | social | delegated`).
 *
 * The hues are the colour-blind-safe Okabe–Ito set and deliberately differ from the Bleu France
 * chrome, so administrative levels never collide with the brand colour. They mirror
 * `styles/tokens.css --niv-*`; React components read them from here (the SSOT) and set colour
 * inline, rather than depending on CSS class suffixes.
 */

export type Level = "state" | "local" | "social" | "delegated";
export type LevelId = Level | "unresolved";
export type LevelShapeKind = "circle" | "square" | "diamond" | "triangle";

export interface LevelMeta {
  id: LevelId;
  label: string;
  /** Categorical hue (Okabe–Ito). */
  color: string;
  /** Tint background for chips/badges. */
  bg: string;
  /** Readable text colour on top of `color` (amber needs dark text for contrast). */
  text: string;
  /** Non-colour cue so the level is distinguishable without relying on hue. */
  shape: LevelShapeKind;
  desc: string;
}

/** Curated `entities.category` value that marks a ministry (a graph root / financeur). */
export const MINISTRY_CATEGORY = "ministère";

export const LEVELS: Record<Level, LevelMeta> = {
  state: {
    id: "state",
    label: "État",
    color: "#0072b2",
    bg: "#e3eef5",
    text: "#ffffff",
    shape: "circle",
    desc: "Administration centrale et opérateurs de l’État",
  },
  local: {
    id: "local",
    label: "Local",
    color: "#009e73",
    bg: "#dcf0e9",
    text: "#ffffff",
    shape: "square",
    desc: "Collectivités territoriales",
  },
  social: {
    id: "social",
    label: "Social",
    color: "#cc79a7",
    bg: "#f7e8f0",
    text: "#ffffff",
    shape: "diamond",
    desc: "Sécurité sociale",
  },
  delegated: {
    id: "delegated",
    label: "Délégué",
    color: "#e69f00",
    bg: "#fbeed4",
    text: "#4a3500",
    shape: "triangle",
    desc: "Opérateurs délégués, titulaires de marchés",
  },
};

/** Neutral grey for an entity whose SIREN is unresolved / outside a bounded fetch. */
export const UNRESOLVED_COLOR = "#b4b4b4";

/**
 * Oversight marker hue — entities « épinglé par la Cour des comptes » (carry ≥1 `mention`, FSC-65).
 * Okabe–Ito vermillion: distinct from every level hue (incl. the delegated amber) and the Bleu
 * France chrome, and colour-blind-safe. SSOT shared by the graph canvas badge + its legend swatch.
 */
export const MENTION_COLOR = "#d55e00";

export const UNRESOLVED_META: LevelMeta = {
  id: "unresolved",
  label: "Non résolu",
  color: UNRESOLVED_COLOR,
  bg: "#eeeeee",
  text: "#666666",
  shape: "circle",
  desc: "Entité non résolue (SIREN manquant)",
};

const isLevel = (value: string): value is Level =>
  Object.prototype.hasOwnProperty.call(LEVELS, value);

/** Look up level metadata, falling back to the neutral "unresolved" meta for unknown/null values. */
export function levelMeta(level: string | null | undefined): LevelMeta {
  return level != null && isLevel(level) ? LEVELS[level] : UNRESOLVED_META;
}
