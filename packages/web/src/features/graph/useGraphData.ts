import { useEffect, useState } from "react";
import { supabase } from "../../lib/supabase";
import {
  buildGraphModel,
  type BudgetRow,
  type EntityRow,
  type GraphEdge,
  type GraphModel,
} from "./graph-model";

export type GraphState =
  | { status: "loading" }
  | { status: "error" }
  | { status: "ready"; model: GraphModel };

/** The institutional perimeter — the nodes the "Graphe institutionnel" shows. */
const INSTITUTIONAL_LEVELS = ["state", "local", "social"];
/** Edge types between institutions; `delegates` (~1.2M buyer→supplier links) is deliberately excluded. */
const INSTITUTIONAL_EDGE_TYPES = ["tutelle", "participation", "funds"];

/**
 * Loads the **institutional** graph (state/local/social entities + the non-delegated edges between
 * them) and builds the force model. At full scale the perimeter is ~150k entities — ~151k of them
 * delegated DECP suppliers — so loading "everything" capped at PostgREST's 1000-row page gave an
 * arbitrary slice. The institutional core is bounded (a few hundred nodes) and complete: every
 * ministry → operator (tutelle), every collectivité, the social module. Delegated suppliers are not
 * in this graph by design — they are reached per-entity via the entity sheet (contracts) and the
 * flux Sankey (the `graph_neighbors` RPC drill-down). All reads go through PostgREST under RLS.
 */
export function useGraphData(): GraphState {
  const [state, setState] = useState<GraphState>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;

    async function load() {
      const [entityRes, edgeRes, budgetRes, mentionRes] = await Promise.all([
        supabase
          .from("entities")
          .select("siren,name,level,category,parent_siren")
          .in("level", INSTITUTIONAL_LEVELS)
          .limit(5000),
        supabase
          .from("edges")
          .select("source_siren,target_siren,type,amount_eur,exercice")
          .in("type", INSTITUTIONAL_EDGE_TYPES)
          .limit(20000),
        supabase.from("budget_facts").select("entity_siren,exercice,amount_cp_eur,executed"),
        // Explicit bound: without it PostgREST applies its ~1k default, which could silently drop
        // mention rows and leave flagged entities un-badged as the table grows.
        supabase.from("mentions").select("entity_siren").limit(50000),
      ]);
      if (cancelled) return;

      // entities/edges/budget are load-bearing — a failure there blanks the graph. The mentions
      // badge is a secondary signal (and the most likely to fail post-deploy, e.g. RLS): treat it
      // as best-effort so a mentions error degrades to "graph without badges", not "no graph".
      if (entityRes.error || edgeRes.error || budgetRes.error) {
        console.error("Graph load failed", {
          entity: entityRes.error,
          edge: edgeRes.error,
          budget: budgetRes.error,
        });
        setState({ status: "error" });
        return;
      }
      if (mentionRes.error) {
        console.error("Graph mentions load failed (badges disabled)", mentionRes.error);
      }

      const entities = (entityRes.data as EntityRow[] | null) ?? [];
      const edges = (edgeRes.data as GraphEdge[] | null) ?? [];
      const budget = (budgetRes.data as BudgetRow[] | null) ?? [];
      const mentionRows = (mentionRes.data as { entity_siren: string | null }[] | null) ?? [];
      const flaggedSirens = new Set(
        mentionRows.map((m) => m.entity_siren).filter((s): s is string => s != null),
      );
      setState({ status: "ready", model: buildGraphModel(entities, edges, budget, flaggedSirens) });
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  return state;
}
