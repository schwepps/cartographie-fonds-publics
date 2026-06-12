import { describe, expect, it } from "vitest";
import {
  buildAdjacency,
  buildGraphModel,
  computeExpandable,
  computeVisible,
  type BudgetRow,
  type EntityRow,
  type GraphEdge,
  type GraphFilters,
} from "./graph-model";

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

const allFilters = (): GraphFilters => ({
  levels: { state: true, local: true, social: true, delegated: true },
  ministry: "all",
  minAmount: 0,
  linkTypes: { tutelle: true, funds: true, participation: true, delegates: true },
});

describe("buildAdjacency", () => {
  it("is undirected and lists a neighbour once per enabled edge", () => {
    const model = buildGraphModel(entities, edges, budget);
    const adj = buildAdjacency(model, allFilters());
    // MESR↔CNRS via both tutelle and funds → CNRS appears twice in MESR's list (and vice-versa).
    expect(adj.get("110044013")).toEqual(["180089013", "180089013"]);
    expect(adj.get("180089013")).toEqual(["110044013", "110044013", "999000999"]);
  });

  it("drops edges whose link type is disabled", () => {
    const model = buildGraphModel(entities, edges, budget);
    const filters = allFilters();
    filters.linkTypes.delegates = false;
    const adj = buildAdjacency(model, filters);
    // The CNRS→999000999 delegates edge is gone, so the unresolved endpoint has no neighbours.
    expect(adj.get("180089013")).toEqual(["110044013", "110044013"]);
    expect(adj.get("999000999")).toEqual([]);
  });
});

describe("computeVisible", () => {
  it("shows only the filter-passing anchors when nothing is expanded", () => {
    const model = buildGraphModel(entities, edges, budget);
    const vis = computeVisible(model, allFilters(), new Set());
    // MESR (ministry) + Région IDF (parentless local) are anchors; CNRS has a parent, 999 is unresolved.
    expect([...vis].sort()).toEqual(["110044013", "237500139"]);
  });

  it("pulls in the filtered neighbours of an expanded node (one hop at a time)", () => {
    const model = buildGraphModel(entities, edges, budget);
    const afterMesr = computeVisible(model, allFilters(), new Set(["110044013"]));
    expect(afterMesr.has("180089013")).toBe(true); // CNRS revealed
    expect(afterMesr.has("999000999")).toBe(false); // CNRS not expanded → its titulaire stays hidden
    const afterBoth = computeVisible(model, allFilters(), new Set(["110044013", "180089013"]));
    expect(afterBoth.has("999000999")).toBe(true); // expanding CNRS reveals the titulaire
  });

  it("honours the level filter at the anchor seed", () => {
    const model = buildGraphModel(entities, edges, budget);
    const filters = allFilters();
    filters.levels.state = false;
    const vis = computeVisible(model, filters, new Set(["110044013"]));
    // State anchors/neighbours are filtered out; only the local anchor remains.
    expect([...vis]).toEqual(["237500139"]);
  });

  it("builds its own adjacency when none is passed (matches the prebuilt path)", () => {
    const model = buildGraphModel(entities, edges, budget);
    const expanded = new Set(["110044013"]);
    const withPrebuilt = computeVisible(
      model,
      allFilters(),
      expanded,
      buildAdjacency(model, allFilters()),
    );
    const withDefault = computeVisible(model, allFilters(), expanded);
    expect([...withDefault].sort()).toEqual([...withPrebuilt].sort());
  });
});

describe("computeExpandable", () => {
  it("flags a visible, unexpanded node that still has a hidden neighbour", () => {
    const model = buildGraphModel(entities, edges, budget);
    const adj = buildAdjacency(model, allFilters());
    const vis = computeVisible(model, allFilters(), new Set(), adj);
    // MESR can be expanded (CNRS hidden); Région IDF has no neighbours so it cannot.
    expect([...computeExpandable(vis, new Set(), adj)]).toEqual(["110044013"]);
  });

  it("excludes already-expanded nodes and surfaces the next frontier", () => {
    const model = buildGraphModel(entities, edges, budget);
    const adj = buildAdjacency(model, allFilters());
    const expanded = new Set(["110044013"]);
    const vis = computeVisible(model, allFilters(), expanded, adj);
    // MESR is expanded → not flagged; CNRS is now the expandable frontier (999 still hidden).
    expect([...computeExpandable(vis, expanded, adj)]).toEqual(["180089013"]);
  });

  it("flags nothing once every visible node's neighbours are also visible", () => {
    const model = buildGraphModel(entities, edges, budget);
    const adj = buildAdjacency(model, allFilters());
    const expanded = new Set(["110044013", "180089013"]);
    const vis = computeVisible(model, allFilters(), expanded, adj);
    expect(computeExpandable(vis, expanded, adj).size).toBe(0);
  });
});
