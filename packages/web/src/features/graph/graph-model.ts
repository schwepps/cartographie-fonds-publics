import Graph from "graphology";

/** A graph node — one institution. The SIREN is the node key (canonical join key). */
export interface GraphNode {
  siren: string;
  name: string;
  level: string | null;
  category: string | null;
}

/** A typed, directed relationship between two institutions (ministry → operator, etc.). */
export interface GraphEdge {
  source_siren: string;
  target_siren: string;
  type: string;
}

/** A row returned by the `graph_neighbors` RPC (depth-capped traversal). */
export interface GraphNeighbourRow {
  source_siren: string;
  target_siren: string;
  type: string;
  amount_eur: number | null;
  hop: number;
}

// DSFR-aligned palette per administrative level; unknown/expanded-but-unfetched nodes fall back.
const LEVEL_COLOR: Record<string, string> = {
  state: "#000091", // bleu France
  local: "#18753c",
  social: "#a558a0",
  delegated: "#b34000",
};
const DEFAULT_COLOR = "#929292";

// Node radius scales with degree so hubs (ministries with many operators) read larger.
const NODE_BASE_SIZE = 6;
const NODE_SIZE_PER_DEGREE = 2;

function colorForLevel(level: string | null): string {
  return (level && LEVEL_COLOR[level]) || DEFAULT_COLOR;
}

/** Stable edge identity so the same (source, target, type) is never added twice. */
export function edgeKey(source: string, target: string, type: string): string {
  return `${source}|${target}|${type}`;
}

/**
 * Deterministic circular coordinates (no `Math.random`, so a render — and its tests — are stable
 * and reproducible). `index`/`count` place the node evenly on a unit circle; the radius lets the
 * caller push expansion nodes onto an outer ring.
 */
function circleCoords(index: number, count: number, radius = 1): { x: number; y: number } {
  const angle = (2 * Math.PI * index) / Math.max(count, 1);
  return { x: Math.cos(angle) * radius, y: Math.sin(angle) * radius };
}

/**
 * Build a graphology graph from curated node/edge rows for Sigma to render. Nodes are placed on a
 * circle in a deterministic (SIREN-sorted) order; size scales with degree so hubs (ministries with
 * many operators) read larger. Edges whose endpoints are not both present are skipped (an edge can
 * reference a SIREN outside a bounded fetch) rather than throwing. The relationship type rides on
 * `label`/`relType` — never the Sigma-reserved `type` attribute.
 */
export function buildGraph(nodes: GraphNode[], edges: GraphEdge[]): Graph {
  const graph = new Graph({ multi: true, type: "directed" });
  const ordered = [...nodes].sort((a, b) => a.siren.localeCompare(b.siren));
  ordered.forEach((node, index) => {
    if (graph.hasNode(node.siren)) return;
    const { x, y } = circleCoords(index, ordered.length);
    // `size` is set by the degree pass below, once all edges exist.
    graph.addNode(node.siren, {
      label: node.name,
      x,
      y,
      color: colorForLevel(node.level),
      level: node.level,
      category: node.category,
    });
  });

  for (const edge of edges) {
    if (!graph.hasNode(edge.source_siren) || !graph.hasNode(edge.target_siren)) continue;
    const key = edgeKey(edge.source_siren, edge.target_siren, edge.type);
    if (graph.hasEdge(key)) continue;
    graph.addEdgeWithKey(key, edge.source_siren, edge.target_siren, {
      label: edge.type,
      relType: edge.type,
    });
  }

  // Degree-based sizing once edges exist — deterministic, gives ministries visual weight.
  graph.forEachNode((node) => {
    graph.setNodeAttribute(
      node,
      "size",
      NODE_BASE_SIZE + NODE_SIZE_PER_DEGREE * graph.degree(node),
    );
  });
  return graph;
}

/**
 * Idempotently fold `graph_neighbors` rows into the existing node/edge arrays. New endpoints become
 * nodes (named from `fetchedNodes`, or the bare SIREN as a last resort); new (source, target, type)
 * triples become edges. Returns fresh arrays only when something changed — when the neighbourhood is
 * already present (the common case on the tiny seed), the originals are returned so callers can skip
 * a re-render. Pure: no Sigma, no network.
 */
export function mergeNeighbourRows(
  nodes: GraphNode[],
  edges: GraphEdge[],
  rows: GraphNeighbourRow[],
  fetchedNodes: GraphNode[],
): { nodes: GraphNode[]; edges: GraphEdge[] } {
  const infoBySiren = new Map(fetchedNodes.map((node) => [node.siren, node]));
  const seenSirens = new Set(nodes.map((node) => node.siren));
  const seenEdges = new Set(
    edges.map((edge) => edgeKey(edge.source_siren, edge.target_siren, edge.type)),
  );

  const nextNodes = [...nodes];
  const nextEdges = [...edges];

  for (const row of rows) {
    for (const siren of [row.source_siren, row.target_siren]) {
      if (seenSirens.has(siren)) continue;
      seenSirens.add(siren);
      nextNodes.push(infoBySiren.get(siren) ?? { siren, name: siren, level: null, category: null });
    }
    const key = edgeKey(row.source_siren, row.target_siren, row.type);
    if (seenEdges.has(key)) continue;
    seenEdges.add(key);
    nextEdges.push({
      source_siren: row.source_siren,
      target_siren: row.target_siren,
      type: row.type,
    });
  }

  if (nextNodes.length === nodes.length && nextEdges.length === edges.length) {
    return { nodes, edges };
  }
  return { nodes: nextNodes, edges: nextEdges };
}
