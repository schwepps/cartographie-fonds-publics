import { describe, expect, it } from "vitest";
import { buildGraph, edgeKey, mergeNeighbourRows } from "./graph-model";
import type { GraphEdge, GraphNeighbourRow, GraphNode } from "./graph-model";

const nodes: GraphNode[] = [
  { siren: "110044013", name: "MESR", level: "state", category: "ministère" },
  { siren: "180089013", name: "CNRS", level: "state", category: "EPST" },
];
const edges: GraphEdge[] = [
  { source_siren: "110044013", target_siren: "180089013", type: "tutelle" },
];

describe("buildGraph", () => {
  it("adds every node and every valid edge", () => {
    const graph = buildGraph(nodes, edges);
    expect(graph.order).toBe(2);
    expect(graph.size).toBe(1);
    expect(graph.hasEdge(edgeKey("110044013", "180089013", "tutelle"))).toBe(true);
  });

  it("skips an edge whose endpoints are not both present (bounded fetch)", () => {
    const graph = buildGraph(nodes, [
      ...edges,
      { source_siren: "110044013", target_siren: "999999999", type: "funds" },
    ]);
    expect(graph.size).toBe(1);
  });

  it("assigns deterministic coordinates and reads the name as the label", () => {
    const a = buildGraph(nodes, edges);
    const b = buildGraph(nodes, edges);
    expect(a.getNodeAttribute("110044013", "x")).toBe(b.getNodeAttribute("110044013", "x"));
    expect(a.getNodeAttribute("180089013", "label")).toBe("CNRS");
  });
});

describe("mergeNeighbourRows", () => {
  const rows: GraphNeighbourRow[] = [
    {
      source_siren: "180089013",
      target_siren: "329200521",
      type: "funds",
      amount_eur: 1000,
      hop: 1,
    },
  ];
  const fetched: GraphNode[] = [
    { siren: "329200521", name: "Fournisseur", level: "delegated", category: null },
  ];

  it("adds a new neighbour node (named) and its edge", () => {
    const out = mergeNeighbourRows(nodes, edges, rows, fetched);
    expect(out.nodes.map((n) => n.siren)).toContain("329200521");
    expect(out.nodes.find((n) => n.siren === "329200521")?.name).toBe("Fournisseur");
    expect(out.edges).toHaveLength(2);
  });

  it("is idempotent — re-merging the same rows yields the same array references", () => {
    const first = mergeNeighbourRows(nodes, edges, rows, fetched);
    const second = mergeNeighbourRows(first.nodes, first.edges, rows, fetched);
    expect(second.nodes).toBe(first.nodes);
    expect(second.edges).toBe(first.edges);
  });

  it("returns the originals when the neighbourhood is already present", () => {
    const out = mergeNeighbourRows(
      nodes,
      edges,
      [
        {
          source_siren: "110044013",
          target_siren: "180089013",
          type: "tutelle",
          amount_eur: null,
          hop: 1,
        },
      ],
      [],
    );
    expect(out.nodes).toBe(nodes);
    expect(out.edges).toBe(edges);
  });
});
