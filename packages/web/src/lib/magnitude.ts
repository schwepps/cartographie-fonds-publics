/**
 * Per-entity "CP magnitude" — a money proxy that drives graph node size and search ranking.
 *
 * The curated `entities` table carries no `cp_eur` column (FSC-49 decision: derive, don't denormalise),
 * so magnitude is the largest of: the entity's latest budget CP, its incoming funding, or its
 * outgoing funding/delegation. That gives ministries (budget), operators (funds in) and financeurs
 * (funds out) all a meaningful size. Returns 0 when nothing is known (→ a default small node).
 */

export interface AmountEdge {
  source_siren: string;
  target_siren: string;
  type: string;
  amount_eur: number | null;
}

const INFLOW_TYPES = new Set(["funds", "participation"]);
const OUTFLOW_TYPES = new Set(["funds", "participation", "delegates"]);

/**
 * Build a `siren → magnitude` map in a single pass over the edges, merged with the per-entity budget
 * CP map. Cheap enough to recompute on the curated graph (tens to low-thousands of edges).
 */
export function buildMagnitudeMap(
  edges: AmountEdge[],
  budgetCpBySiren: Map<string, number> = new Map(),
): Map<string, number> {
  const inflow = new Map<string, number>();
  const outflow = new Map<string, number>();
  const add = (m: Map<string, number>, key: string, value: number) =>
    m.set(key, (m.get(key) ?? 0) + value);

  for (const edge of edges) {
    const amount = edge.amount_eur ?? 0;
    if (amount <= 0) continue;
    if (INFLOW_TYPES.has(edge.type)) add(inflow, edge.target_siren, amount);
    if (OUTFLOW_TYPES.has(edge.type)) add(outflow, edge.source_siren, amount);
  }

  const out = new Map<string, number>();
  const keys = new Set<string>([...budgetCpBySiren.keys(), ...inflow.keys(), ...outflow.keys()]);
  for (const key of keys) {
    out.set(
      key,
      Math.max(budgetCpBySiren.get(key) ?? 0, inflow.get(key) ?? 0, outflow.get(key) ?? 0),
    );
  }
  return out;
}

const NODE_MIN_RADIUS = 6;
const NODE_MAX_RADIUS = 34;

/**
 * Graph node radius from a CP magnitude: `6 + log10(cp) * 2.6`, clamped to `[6, 34]` (ported from
 * `design/js/graph.jsx`). A zero/unknown magnitude gets a small fixed radius.
 */
export function radiusForCp(cp: number): number {
  if (cp <= 0) return 7;
  return Math.max(NODE_MIN_RADIUS, Math.min(NODE_MAX_RADIUS, 6 + Math.log10(cp) * 2.6));
}

export interface BudgetCpRow {
  entity_siren: string | null;
  exercice: number;
  amount_cp_eur: number | null;
  executed: boolean;
}

/**
 * Sum of voted CP for each entity's latest exercice — the budget side of its magnitude. Shared by
 * the graph model + the search ranking so the "latest voted exercice" rule lives in one place.
 */
export function budgetCpBySiren(budget: BudgetCpRow[]): Map<string, number> {
  const latest = new Map<string, number>();
  for (const row of budget) {
    if (row.executed || row.entity_siren == null) continue;
    latest.set(row.entity_siren, Math.max(latest.get(row.entity_siren) ?? 0, row.exercice));
  }
  const cp = new Map<string, number>();
  for (const row of budget) {
    if (row.executed || row.entity_siren == null) continue;
    if (row.exercice !== latest.get(row.entity_siren)) continue;
    cp.set(row.entity_siren, (cp.get(row.entity_siren) ?? 0) + (row.amount_cp_eur ?? 0));
  }
  return cp;
}
