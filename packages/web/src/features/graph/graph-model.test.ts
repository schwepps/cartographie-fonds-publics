import { describe, expect, it } from "vitest";
import { buildGraphModel, type BudgetRow, type EntityRow, type GraphEdge } from "./graph-model";

const entities: EntityRow[] = [
  { siren: "110044013", name: "MESR", level: "state", category: "ministère", parent_siren: null },
  { siren: "180089013", name: "CNRS", level: "state", category: "EPST", parent_siren: "110044013" },
  {
    siren: "237500139",
    name: "Région IDF",
    level: "local",
    category: "Région",
    parent_siren: null,
  },
];
const edges: GraphEdge[] = [
  {
    source_siren: "110044013",
    target_siren: "180089013",
    type: "tutelle",
    amount_eur: null,
    exercice: null,
  },
  {
    source_siren: "110044013",
    target_siren: "180089013",
    type: "funds",
    amount_eur: 2_950_000_000,
    exercice: 2025,
  },
  {
    source_siren: "180089013",
    target_siren: "999000999",
    type: "delegates",
    amount_eur: 1_800_000,
    exercice: 2026,
  },
];
const budget: BudgetRow[] = [
  { entity_siren: "110044013", exercice: 2025, amount_cp_eur: 26_000_000_000, executed: false },
];

describe("buildGraphModel", () => {
  it("adds an unresolved placeholder for an edge endpoint with no entity row", () => {
    const placeholder = buildGraphModel(entities, edges, budget).byId.get("999000999");
    expect(placeholder?.resolved).toBe(false);
    expect(placeholder?.name).toBe("999000999");
    expect(placeholder?.cluster).toBe("grp_unresolved");
  });

  it("clusters state entities by root ministry and others by level", () => {
    const { byId } = buildGraphModel(entities, edges, budget);
    expect(byId.get("180089013")?.cluster).toBe("110044013"); // CNRS → its ministry
    expect(byId.get("110044013")?.cluster).toBe("110044013"); // ministry is its own root
    expect(byId.get("237500139")?.cluster).toBe("grp_local");
  });

  it("marks parentless, non-delegated entities as anchors", () => {
    const { byId } = buildGraphModel(entities, edges, budget);
    expect(byId.get("110044013")?.isAnchor).toBe(true);
    expect(byId.get("237500139")?.isAnchor).toBe(true);
    expect(byId.get("180089013")?.isAnchor).toBe(false); // has a parent
  });

  it("derives CP magnitude from budget (ministry) and funds inflow (operator)", () => {
    const { byId } = buildGraphModel(entities, edges, budget);
    expect(byId.get("110044013")?.cp).toBe(26_000_000_000);
    expect(byId.get("180089013")?.cp).toBe(2_950_000_000);
  });

  it("keeps every edge and counts degree across endpoints", () => {
    const { byId, edges: kept } = buildGraphModel(entities, edges, budget);
    expect(kept).toHaveLength(3);
    expect(byId.get("180089013")?.degree).toBe(3); // tutelle + funds in, delegates out
  });
});
