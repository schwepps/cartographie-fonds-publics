import { useEffect, useState } from "react";
import { supabase } from "../../lib/supabase";
import { buildFlowLinks, type FlowEdge, type FlowEntity, type SankeyLink } from "../../lib/flows";

/** Ministry whose funding flows seed the landing teaser (ESR — the richest funds cluster). */
const TEASER_MINISTRY = "110044013";

/** Exercice the headline budget figure sums (voted LFI). */
const BUDGET_EXERCICE = 2025;

interface EntityRow {
  siren: string;
  name: string;
  level: string | null;
  parent_siren: string | null;
}
interface BudgetRow {
  exercice: number;
  amount_cp_eur: number | null;
  executed: boolean;
}

export interface OverviewFigures {
  budgetCp: number;
  institutions: number;
  operateurs: number;
  contrats: number;
}

export type OverviewState =
  | { status: "loading" }
  | { status: "error" }
  | { status: "ready"; figures: OverviewFigures; teaser: { name: string; links: SankeyLink[] } };

/**
 * Landing-overview data: headline counts + the voted budget-CP total + the teaser ministry's
 * funding flows. The curated graph is small (seed/demo scale), so it fetches entities + edges in
 * full and computes the figures client-side — all reads straight through PostgREST under RLS.
 */
export function useOverview(): OverviewState {
  const [state, setState] = useState<OverviewState>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;

    async function load() {
      const [entityRes, edgeRes, budgetRes, contractRes] = await Promise.all([
        supabase.from("entities").select("siren,name,level,parent_siren"),
        supabase.from("edges").select("source_siren,target_siren,type,amount_eur,exercice"),
        supabase.from("budget_facts").select("exercice,amount_cp_eur,executed"),
        supabase.from("contracts").select("*", { count: "exact", head: true }),
      ]);
      if (cancelled) return;

      if (entityRes.error || edgeRes.error || budgetRes.error || contractRes.error) {
        console.error("Overview load failed", {
          entity: entityRes.error,
          edge: edgeRes.error,
          budget: budgetRes.error,
          contract: contractRes.error,
        });
        setState({ status: "error" });
        return;
      }

      const entities = (entityRes.data as EntityRow[] | null) ?? [];
      const edges = (edgeRes.data as FlowEdge[] | null) ?? [];
      const budget = (budgetRes.data as BudgetRow[] | null) ?? [];

      const figures: OverviewFigures = {
        budgetCp: budget
          .filter((b) => !b.executed && b.exercice === BUDGET_EXERCICE)
          .reduce((sum, b) => sum + (b.amount_cp_eur ?? 0), 0),
        institutions: entities.length,
        operateurs: entities.filter((e) => e.parent_siren != null || e.level === "delegated")
          .length,
        contrats: contractRes.count ?? 0,
      };

      const entityBySiren = new Map<string, FlowEntity>(
        entities.map((e) => [e.siren, { siren: e.siren, name: e.name, level: e.level }]),
      );
      const teaser = entityBySiren.get(TEASER_MINISTRY);

      setState({
        status: "ready",
        figures,
        teaser: {
          name: teaser?.name ?? "",
          links: buildFlowLinks(TEASER_MINISTRY, edges, entityBySiren),
        },
      });
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  return state;
}
