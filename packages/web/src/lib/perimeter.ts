/**
 * Anti-double-counting perimeters (FSC-42) — the browser mirror of `core.methodology`.
 *
 * Public money lives in several accounting universes that are NOT consolidatable into one figure
 * (État/LOLF, collectivités/M57·M14, sécurité sociale). The Python side is authoritative and keys on
 * `BudgetFact.nomenclature`; in the browser the entity `level` is the universe proxy. Keep the two
 * mappings in sync. `delegated` operators are *recipients*, not a budget universe, so they never
 * alone make a total "mixed".
 */
import type { Level } from "./levels";

export const UNIVERSE_LOLF = "État (LOLF)";
export const UNIVERSE_M57 = "Collectivités (M57/M14)";
export const UNIVERSE_SOCIAL = "Sécurité sociale";

const UNIVERSE_BY_LEVEL: Record<Level, string | null> = {
  state: UNIVERSE_LOLF,
  local: UNIVERSE_M57,
  social: UNIVERSE_SOCIAL,
  delegated: null,
};

/** The budget universe an entity's level implies, or `null` for `delegated` / unknown levels. */
export function universeForLevel(level: string | null | undefined): string | null {
  // Own-property check (mirrors levels.ts `isLevel`): `in` would also match inherited keys like
  // `toString`/`__proto__`, so an unexpected level string could resolve to a non-universe value.
  return level != null && Object.prototype.hasOwnProperty.call(UNIVERSE_BY_LEVEL, level)
    ? UNIVERSE_BY_LEVEL[level as Level]
    : null;
}

/** True when the levels span more than one budget universe — a total over them must carry the note. */
export function mixesPerimeters(levels: Iterable<string | null | undefined>): boolean {
  const universes = new Set<string>();
  for (const level of levels) {
    const universe = universeForLevel(level);
    if (universe) universes.add(universe);
  }
  return universes.size > 1;
}
