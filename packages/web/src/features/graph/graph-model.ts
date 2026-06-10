import { acronymOf } from "../../lib/acronyms";
import { MINISTRY_CATEGORY } from "../../lib/levels";
import { budgetCpBySiren, buildMagnitudeMap, type AmountEdge } from "../../lib/magnitude";
import { tutelleChain } from "../../lib/tutelle";

/** A graph node — an institution (or an unresolved edge endpoint). Physics fields are mutated by the
 *  force simulation; everything else is derived once by {@link buildGraphModel}. */
export interface GraphNode {
  siren: string;
  name: string;
  level: string | null;
  category: string | null;
  parent_siren: string | null;
  /** CP magnitude (budget / funds) — drives node radius. */
  cp: number;
  acronym: string | null;
  /** false → an edge endpoint with no entity row (« SIREN non résolu »). */
  resolved: boolean;
  /** Cluster key: the root ministry SIREN for State entities, else `grp_<level>`. */
  cluster: string;
  /** Roots that seed the visible set (ministries, caisses, collectivités). */
  isAnchor: boolean;
  isMinistry: boolean;
  degree: number;
  // Mutable simulation state.
  x?: number;
  y?: number;
  vx?: number;
  vy?: number;
}

export interface GraphEdge extends AmountEdge {
  exercice: number | null;
}

export interface GraphModel {
  nodes: GraphNode[];
  byId: Map<string, GraphNode>;
  edges: GraphEdge[];
}

export interface EntityRow {
  siren: string;
  name: string;
  level: string | null;
  category: string | null;
  parent_siren: string | null;
}

export interface BudgetRow {
  entity_siren: string | null;
  exercice: number;
  amount_cp_eur: number | null;
  executed: boolean;
}

export interface GraphFilters {
  levels: Record<string, boolean>;
  ministry: string;
  minAmount: number;
  linkTypes: Record<string, boolean>;
}

/**
 * Visibility predicate shared by the canvas and the table view (so they never desync): a level
 * toggle, a tutelle-chain match for the ministry filter, and a CP floor that ministries are exempt
 * from.
 */
export function passFilter(
  node: GraphNode,
  filters: GraphFilters,
  byId: Map<string, GraphNode>,
): boolean {
  if (node.level && !filters.levels[node.level]) return false;
  if (filters.ministry !== "all" && node.level === "state") {
    if (tutelleChain(node.siren, byId)[0]?.siren !== filters.ministry) return false;
  }
  if (filters.minAmount > 0 && node.cp < filters.minAmount && !node.isMinistry) return false;
  return true;
}

/**
 * Build the force-graph model from curated rows: derive each entity's CP magnitude, add unresolved
 * placeholder nodes for edge endpoints with no entity row, then compute the cluster / anchor /
 * degree fields the layout + visibility logic need. Pure and deterministic — unit-tested.
 */
export function buildGraphModel(
  entities: EntityRow[],
  edges: GraphEdge[],
  budget: BudgetRow[] = [],
): GraphModel {
  const magnitude = buildMagnitudeMap(edges, budgetCpBySiren(budget));

  const byId = new Map<string, GraphNode>();
  for (const e of entities) {
    byId.set(e.siren, {
      siren: e.siren,
      name: e.name,
      level: e.level,
      category: e.category,
      parent_siren: e.parent_siren,
      cp: magnitude.get(e.siren) ?? 0,
      acronym: acronymOf(e.siren),
      resolved: true,
      cluster: "",
      isAnchor: false,
      isMinistry: e.category === MINISTRY_CATEGORY,
      degree: 0,
    });
  }

  // Unresolved placeholders: an edge endpoint with no entity row (e.g. a DECP titulaire).
  for (const edge of edges) {
    for (const siren of [edge.source_siren, edge.target_siren]) {
      if (byId.has(siren)) continue;
      byId.set(siren, {
        siren,
        name: siren,
        level: null,
        category: null,
        parent_siren: null,
        cp: magnitude.get(siren) ?? 0,
        acronym: null,
        resolved: false,
        cluster: "grp_unresolved",
        isAnchor: false,
        isMinistry: false,
        degree: 0,
      });
    }
  }

  // Keep only edges whose endpoints both exist (always true now placeholders are added).
  const keptEdges = edges.filter((e) => byId.has(e.source_siren) && byId.has(e.target_siren));
  for (const edge of keptEdges) {
    const s = byId.get(edge.source_siren);
    const t = byId.get(edge.target_siren);
    if (s) s.degree += 1;
    if (t) t.degree += 1;
  }

  for (const node of byId.values()) {
    if (node.cluster === "grp_unresolved") continue;
    const root = tutelleChain(node.siren, byId)[0];
    node.cluster =
      node.level === "state" ? (root?.siren ?? node.siren) : `grp_${node.level ?? "x"}`;
    node.isAnchor = node.parent_siren == null && node.level != null && node.level !== "delegated";
  }

  return { nodes: [...byId.values()], byId, edges: keptEdges };
}
