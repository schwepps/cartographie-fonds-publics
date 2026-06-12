import { bench, describe } from "vitest";
import { buildFlowLinks, type FlowEdge, type FlowEntity } from "../../lib/flows";
import { computeSankey } from "../../lib/ui/Sankey";
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

/**
 * Micro-benchmarks for the graph + Sankey hot paths (FSC-60). The curated État-central + delegated
 * dataset is hundreds of nodes, so these run a synthetic graph an order of magnitude larger than the
 * demo seed (169 nodes / 102 edges): a "full" tier of ~1 600 nodes / ~1 700 edges and a stress tier
 * of ~3 200 / ~3 400, to confirm the pure compute stays well within the interaction budget. Run with
 * `pnpm bench`; numbers are recorded in `docs/perf-graph-sankey.md`. The generator is deterministic
 * (no RNG) so runs are comparable.
 */
const pad = (n: number): string => n.toString().padStart(9, "0");

interface SyntheticGraph {
  entities: EntityRow[];
  edges: GraphEdge[];
  budget: BudgetRow[];
}

/**
 * A ministry → operator → titulaire shaped graph: each ministry funds N operators (tutelle + funds
 * edges), each operator delegates to M titulaires (only every 4th titulaire gets an entity row, the
 * rest stay unresolved DECP endpoints — mirroring the real shape), plus parentless local entities.
 */
function generateGraph(opts: {
  ministries: number;
  operatorsPer: number;
  titulairesPer: number;
  locals: number;
}): SyntheticGraph {
  const entities: EntityRow[] = [];
  const edges: GraphEdge[] = [];
  const budget: BudgetRow[] = [];
  let id = 100_000_000;
  const next = () => pad(id++);

  for (let m = 0; m < opts.ministries; m++) {
    const min = next();
    entities.push({
      siren: min,
      name: `Ministère ${m}`,
      level: "state",
      category: "ministère",
      parent_siren: null,
    });
    budget.push({
      entity_siren: min,
      exercice: 2025,
      amount_cp_eur: 1e9 + m * 1e8,
      executed: false,
    });
    for (let o = 0; o < opts.operatorsPer; o++) {
      const op = next();
      entities.push({
        siren: op,
        name: `Opérateur ${m}-${o}`,
        level: "state",
        category: "EPST",
        parent_siren: min,
      });
      edges.push({
        source_siren: min,
        target_siren: op,
        type: "tutelle",
        amount_eur: null,
        exercice: null,
      });
      edges.push({
        source_siren: min,
        target_siren: op,
        type: "funds",
        amount_eur: 1e7 + o * 1e6,
        exercice: 2025,
      });
      for (let t = 0; t < opts.titulairesPer; t++) {
        const tit = next();
        edges.push({
          source_siren: op,
          target_siren: tit,
          type: "delegates",
          amount_eur: 1e5 + t * 1e3,
          exercice: 2026,
        });
        if (t % 4 === 0) {
          entities.push({
            siren: tit,
            name: `Titulaire ${m}-${o}-${t}`,
            level: "delegated",
            category: "entreprise",
            parent_siren: null,
          });
        }
      }
    }
  }
  for (let l = 0; l < opts.locals; l++) {
    entities.push({
      siren: next(),
      name: `Collectivité ${l}`,
      level: "local",
      category: "Commune",
      parent_siren: null,
    });
  }
  return { entities, edges, budget };
}

const ALL_FILTERS: GraphFilters = {
  levels: { state: true, local: true, social: true, delegated: true },
  ministry: "all",
  minAmount: 0,
  linkTypes: { tutelle: true, funds: true, participation: true, delegates: true },
};

const TIERS = {
  full: { ministries: 12, operatorsPer: 10, titulairesPer: 12, locals: 50 },
  stress: { ministries: 24, operatorsPer: 10, titulairesPer: 12, locals: 100 },
} as const;

for (const [tier, opts] of Object.entries(TIERS)) {
  const { entities, edges, budget } = generateGraph(opts);
  const model = buildGraphModel(entities, edges, budget);
  // Expand every node so the visible set hits its worst case ("Tout déplier").
  const expanded = new Set(model.nodes.map((n) => n.siren));
  const adj = buildAdjacency(model, ALL_FILTERS);
  // A realistic *interactive* state for computeExpandable: only the anchors are expanded, so many
  // visible operators are unexpanded-with-hidden-neighbours — the case that actually scans the
  // adjacency (with everything expanded it would early-`continue` and measure an empty loop).
  const anchorsExpanded = new Set(model.nodes.filter((n) => n.isAnchor).map((n) => n.siren));
  const partialVisible = computeVisible(model, ALL_FILTERS, anchorsExpanded, adj);

  const flowEntities = new Map<string, FlowEntity>(
    entities.map((e) => [e.siren, { siren: e.siren, name: e.name, level: e.level }]),
  );
  const flowEdges: FlowEdge[] = edges.map((e) => ({
    source_siren: e.source_siren,
    target_siren: e.target_siren,
    type: e.type,
    amount_eur: e.amount_eur,
    exercice: e.exercice,
  }));
  const ministrySiren = entities[0].siren;
  const links = buildFlowLinks(ministrySiren, flowEdges, flowEntities);

  describe(`graph hot paths — ${tier} (${model.nodes.length} nodes / ${model.edges.length} edges)`, () => {
    bench("buildGraphModel", () => {
      buildGraphModel(entities, edges, budget);
    });
    bench("buildAdjacency + computeVisible", () => {
      computeVisible(model, ALL_FILTERS, expanded, buildAdjacency(model, ALL_FILTERS));
    });
    bench("computeExpandable (anchors-only expanded)", () => {
      computeExpandable(partialVisible, anchorsExpanded, adj);
    });
    bench(`buildFlowLinks (${links.length} links)`, () => {
      buildFlowLinks(ministrySiren, flowEdges, flowEntities);
    });
    bench("computeSankey", () => {
      computeSankey(links, 900, 460, 28);
    });
  });
}
