import { describe, expect, it } from "vitest";
import { buildMagnitudeMap, radiusForCp, type AmountEdge } from "./magnitude";
import { buildFlowLinks, type FlowEdge, type FlowEntity } from "./flows";
import { computeSankey } from "./ui/Sankey";

describe("buildMagnitudeMap", () => {
  const edges: AmountEdge[] = [
    { source_siren: "A", target_siren: "B", type: "funds", amount_eur: 100 },
    { source_siren: "B", target_siren: "T", type: "delegates", amount_eur: 30 },
    { source_siren: "A", target_siren: "B", type: "tutelle", amount_eur: null },
  ];

  it("takes the max of budget CP, inflow and outflow per entity", () => {
    const map = buildMagnitudeMap(edges, new Map([["A", 500]]));
    expect(map.get("A")).toBe(500); // budget 500 > out 100
    expect(map.get("B")).toBe(100); // in 100 > out 30
  });

  it("ignores non-positive amounts and unknown directions", () => {
    const map = buildMagnitudeMap(edges);
    expect(map.get("A")).toBe(100); // only the funds outflow
    expect(map.has("T")).toBe(false); // delegates target is not an inflow
  });
});

describe("radiusForCp", () => {
  it("returns a small fixed radius for zero/unknown magnitude", () => {
    expect(radiusForCp(0)).toBe(7);
  });
  it("grows with log10 and clamps to [6, 34]", () => {
    expect(radiusForCp(1)).toBeCloseTo(6, 5);
    expect(radiusForCp(1e9)).toBeCloseTo(29.4, 5);
    expect(radiusForCp(1e30)).toBe(34);
  });
});

const ENTITIES = new Map<string, FlowEntity>([
  ["M", { siren: "M", name: "Ministère", level: "state" }],
  ["O", { siren: "O", name: "Opérateur", level: "state" }],
]);
const FLOW_EDGES: FlowEdge[] = [
  { source_siren: "M", target_siren: "O", type: "funds", amount_eur: 100, exercice: 2025 },
  { source_siren: "O", target_siren: "T", type: "delegates", amount_eur: 30, exercice: 2026 },
  { source_siren: "M", target_siren: "O", type: "tutelle", amount_eur: null, exercice: null },
];

describe("buildFlowLinks", () => {
  it("builds a two-hop financeur → opérateur → titulaire flow", () => {
    const links = buildFlowLinks("M", FLOW_EDGES, ENTITIES);
    expect(links).toHaveLength(2);
    expect(links[0]).toMatchObject({
      source: "M",
      target: "O",
      sourceCol: 0,
      targetCol: 1,
      type: "funds",
    });
    // Unresolved titulaire (no entity row) keeps its bare SIREN label.
    expect(links[1]).toMatchObject({
      source: "O",
      target: "T",
      targetCol: 2,
      type: "delegates",
      targetLabel: "T",
    });
  });

  it("returns nothing for an unknown root", () => {
    expect(buildFlowLinks("ZZZ", FLOW_EDGES, ENTITIES)).toEqual([]);
  });

  it("anchors on an operator root: incoming funds + its outgoing delegates", () => {
    // "O" has no outgoing funds, so it is treated as an operator: M → O (funds) + O → T (delegates).
    const links = buildFlowLinks("O", FLOW_EDGES, ENTITIES);
    expect(links).toHaveLength(2);
    expect(links[0]).toMatchObject({ source: "M", target: "O", sourceCol: 0, type: "funds" });
    expect(links[1]).toMatchObject({ source: "O", target: "T", targetCol: 2, type: "delegates" });
  });

  it("shows an operator's delegates even with no funds layer (real-data case)", () => {
    // Only a delegates edge exists (no funds yet) — focusing on the operator still surfaces it.
    const delegatesOnly: FlowEdge[] = [
      { source_siren: "O", target_siren: "T", type: "delegates", amount_eur: 30, exercice: 2026 },
    ];
    const links = buildFlowLinks("O", delegatesOnly, ENTITIES);
    expect(links).toHaveLength(1);
    expect(links[0]).toMatchObject({ source: "O", target: "T", sourceCol: 1, targetCol: 2 });
  });
});

describe("computeSankey", () => {
  it("derives nodes/columns and sizes nodes by max(in, out)", () => {
    const links = buildFlowLinks("M", FLOW_EDGES, ENTITIES);
    const layout = computeSankey(links, 900, 400, 28);
    expect(layout.nodes.map((n) => n.id).sort()).toEqual(["M", "O", "T"]);
    expect(layout.nodeById.get("M")?.col).toBe(0);
    expect(layout.nodeById.get("O")?.value).toBe(100);
    expect(layout.nodeById.get("T")?.value).toBe(30);
    // every link gets a positive stroke width + vertical endpoints.
    expect(
      layout.links.every((l) => l.sw > 0 && Number.isFinite(l.sy0) && Number.isFinite(l.ty0)),
    ).toBe(true);
  });
});
