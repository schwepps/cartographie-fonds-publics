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

/** A `funds`/`delegates` link with column-positioned, labelled endpoints. Col 2 (titulaire) keeps a
 * full name; cols 0–1 use the compact acronym label. An un-named target keeps its bare SIREN. */
function makeLink(
  edge: FlowEdge,
  amount: number,
  sourceCol: number,
  source: FlowEntity,
  target: FlowEntity | undefined,
): SankeyLink {
  const targetCol = sourceCol + 1;
  return {
    source: edge.source_siren,
    target: edge.target_siren,
    value: amount,
    type: edge.type,
    exercice: edge.exercice,
    sourceCol,
    sourceLabel: shortLabel(source.siren, source.name),
    sourceLevel: source.level,
    targetCol,
    targetLabel: target
      ? targetCol === 2
        ? target.name
        : shortLabel(target.siren, target.name)
      : edge.target_siren,
    targetLevel: target ? target.level : null,
  };
}

/** Each `delegates` edge from `operatorSiren` → its titulaires, on the given columns. */
function delegatesFrom(
  operatorSiren: string,
  operator: FlowEntity,
  sourceCol: number,
  edges: FlowEdge[],
  entityBySiren: Map<string, FlowEntity>,
): SankeyLink[] {
  return edges
    .filter(
      (e) => e.source_siren === operatorSiren && e.type === "delegates" && positive(e.amount_eur),
    )
    .map((e) =>
      makeLink(e, e.amount_eur as number, sourceCol, operator, entityBySiren.get(e.target_siren)),
    );
}

/**
 * Build the funding-flow links for a selected entity. Two shapes depending on the root:
 *
 * - **Financeur root** (has outgoing `funds`, e.g. a ministry): `funds` edges (col 0 → 1), then each
 *   funded operator's `delegates` edges (col 1 → 2) — the full public → opérateur → titulaire chain.
 * - **Operator root** (no outgoing `funds`, e.g. an opérateur): its incoming `funds` (financeur →
 *   opérateur, col 0 → 1) plus its own outgoing `delegates` (col 1 → 2), anchoring the operator in
 *   the middle. This is what surfaces real `delegates` edges when no `funds` layer exists yet.
 *
 * Unresolved titulaires (no entity row) keep their bare SIREN label.
 */
export function buildFlowLinks(
  rootSiren: string,
  edges: FlowEdge[],
  entityBySiren: Map<string, FlowEntity>,
): SankeyLink[] {
  const root = entityBySiren.get(rootSiren);
  if (!root) return [];

  const hasOutgoingFunds = edges.some(
    (e) => e.source_siren === rootSiren && e.type === "funds" && positive(e.amount_eur),
  );

  if (hasOutgoingFunds) {
    const links: SankeyLink[] = [];
    for (const fund of edges) {
      if (fund.source_siren !== rootSiren || fund.type !== "funds" || !positive(fund.amount_eur)) {
        continue;
      }
      const operator = entityBySiren.get(fund.target_siren);
      if (!operator) continue;
      links.push(makeLink(fund, fund.amount_eur, 0, root, operator));
      links.push(...delegatesFrom(fund.target_siren, operator, 1, edges, entityBySiren));
    }
    return links;
  }

  // Operator-anchored: incoming funding (financeur → operator) + outgoing delegations.
  const incoming = edges
    .filter((e) => e.target_siren === rootSiren && e.type === "funds" && positive(e.amount_eur))
    .flatMap((e) => {
      const financeur = entityBySiren.get(e.source_siren);
      return financeur ? [makeLink(e, e.amount_eur as number, 0, financeur, root)] : [];
    });
  return [...incoming, ...delegatesFrom(rootSiren, root, 1, edges, entityBySiren)];
}
