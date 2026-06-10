/**
 * fr-FR money formatters, ported from the delivered `design/` export (`util.js`). Amounts are in
 * euros. `null`/`undefined` render as « — » (an em dash), never as "0" — `0` is a real value and is
 * formatted as such.
 */

/**
 * Compact euro amount for dense surfaces (cards, table cells, tooltips):
 * `31,2 Md€` · `254 M€` · `84 925 €` · `12,50 €`. Sub-10 M€ keeps one decimal; above that it rounds.
 */
export function euroCompact(value: number | null | undefined): string {
  if (value == null) return "—";
  const abs = Math.abs(value);
  if (abs >= 1e9) {
    return `${(value / 1e9).toLocaleString("fr-FR", { maximumFractionDigits: 1 })} Md€`;
  }
  if (abs >= 1e6) {
    return `${(value / 1e6).toLocaleString("fr-FR", { maximumFractionDigits: abs < 1e7 ? 1 : 0 })} M€`;
  }
  if (abs >= 1e3) {
    return `${Math.round(value).toLocaleString("fr-FR")} €`;
  }
  return `${value.toLocaleString("fr-FR", { maximumFractionDigits: 2 })} €`;
}

/** Full euro amount with thousands separators (no magnitude suffix): `84 925 €`. */
export function euroFull(value: number | null | undefined): string {
  return value == null ? "—" : `${value.toLocaleString("fr-FR", { maximumFractionDigits: 2 })} €`;
}
