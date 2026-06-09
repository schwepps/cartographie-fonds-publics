/**
 * Build funding-flow links (financeur → opérateur → titulaire) for the Sankey diagram, shared by the
 * Flux screen, the home teaser and the fiche mini-flux. Pure: takes curated edges + an entity index
 * and returns the column-assigned links the Sankey lays out. Ported from `design/js/sankey.jsx`.
 */
import { shortLabel } from "./acronyms";

export interface FlowEntity {
  siren: string;
  name: string;
  level: string | null;
}

export interface FlowEdge {
  source_siren: string;
  target_siren: string;
  type: string;
  amount_eur: number | null;
  exercice: number | null;
}

export interface SankeyLink {
  source: string;
  target: string;
  value: number;
  type: string;
  exercice: number | null;
  sourceCol: number;
  sourceLabel: string;
  sourceLevel: string | null;
  targetCol: number;
  targetLabel: string;
  targetLevel: string | null;
}

const positive = (amount: number | null): amount is number => (amount ?? 0) > 0;

/**
 * Two-hop flow from a root financeur: `funds` edges (col 0 → 1), then each funded operator's
 * `delegates` edges (col 1 → 2). Unresolved titulaires (no entity row) keep their bare SIREN label.
 */
export function buildFlowLinks(
  rootSiren: string,
  edges: FlowEdge[],
  entityBySiren: Map<string, FlowEntity>,
): SankeyLink[] {
  const links: SankeyLink[] = [];
  const root = entityBySiren.get(rootSiren);
  if (!root) return links;

  for (const fund of edges) {
    if (fund.source_siren !== rootSiren || fund.type !== "funds" || !positive(fund.amount_eur)) {
      continue;
    }
    const operator = entityBySiren.get(fund.target_siren);
    if (!operator) continue;
    links.push({
      source: rootSiren,
      target: fund.target_siren,
      value: fund.amount_eur,
      type: "funds",
      exercice: fund.exercice,
      sourceCol: 0,
      sourceLabel: shortLabel(root.siren, root.name),
      sourceLevel: root.level,
      targetCol: 1,
      targetLabel: shortLabel(operator.siren, operator.name),
      targetLevel: operator.level,
    });

    for (const delegation of edges) {
      if (
        delegation.source_siren !== fund.target_siren ||
        delegation.type !== "delegates" ||
        !positive(delegation.amount_eur)
      ) {
        continue;
      }
      const titulaire = entityBySiren.get(delegation.target_siren);
      links.push({
        source: fund.target_siren,
        target: delegation.target_siren,
        value: delegation.amount_eur,
        type: "delegates",
        exercice: delegation.exercice,
        sourceCol: 1,
        sourceLabel: shortLabel(operator.siren, operator.name),
        sourceLevel: operator.level,
        targetCol: 2,
        targetLabel: titulaire ? titulaire.name : delegation.target_siren,
        targetLevel: titulaire ? titulaire.level : null,
      });
    }
  }
  return links;
}
