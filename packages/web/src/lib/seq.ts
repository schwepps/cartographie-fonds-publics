/**
 * Sequential single-hue blue ramp for shading amounts (0 → 1). Distinct from the categorical
 * level palette in `levels.ts`; mirrors `styles/tokens.css --seq-*`. Ported from the `design/`
 * export (`util.js`).
 */
export const SEQ = ["#eef3f9", "#cfe0ef", "#9cc1df", "#5e95c7", "#2e6ca8", "#103e6e"] as const;

/** Map a normalised magnitude `t` (clamped to [0, 1]) to a ramp swatch. */
export function seqColor(t: number): string {
  const clamped = Math.max(0, Math.min(1, t));
  const index = Math.min(SEQ.length - 1, Math.floor(clamped * (SEQ.length - 1)));
  return SEQ[index];
}
