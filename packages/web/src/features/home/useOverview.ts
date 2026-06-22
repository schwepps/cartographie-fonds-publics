import { useEffect, useState } from "react";
import { supabase } from "../../lib/supabase";
import { buildFlowLinks, type FlowEdge, type FlowEntity, type SankeyLink } from "../../lib/flows";

/** Ministry whose funding flows seed the landing teaser (ESR — the richest funds cluster). */
const TEASER_MINISTRY = "110044013";

/** Exercice the headline budget figure sums (voted LFI). */
const BUDGET_EXERCICE = 2025;

interface BudgetRow {
  exercice: number;
  amount_cp_eur: number | null;
  executed: boolean;
  nomenclature: string | null;
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
 * funding flows. Counts come from server-side `count` queries (the full perimeter is ~150k entities
 * / ~2M contracts — far past PostgREST's default 1000-row page, so client-side `.length` would
 * silently undercount). The teaser edges are scoped to the one ministry rather than fetching the
 * whole ~1.2M-edge graph. All reads go straight through PostgREST under RLS.
 */
export function useOverview(): OverviewState {
  const [state, setState] = useState<OverviewState>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;

    async function load() {
      const teaserScope = `source_siren.eq.${TEASER_MINISTRY},target_siren.eq.${TEASER_MINISTRY}`;
      const [budgetRes, instRes, opRes, contractRes, teaserEdgeRes] = await Promise.all([
        // Budget facts are few (hundreds), so fetch + sum client-side (pinned to voted LOLF below).
        supabase.from("budget_facts").select("exercice,amount_cp_eur,executed,nomenclature"),
        // Institutions = the institutional perimeter (state + local + social), not the ~150k
        // delegated suppliers. Count server-side so it is not capped at the 1000-row page.
        supabase
          .from("entities")
          .select("*", { count: "exact", head: true })
          .in("level", ["state", "local", "social"]),
        // Opérateurs & délégataires = operators under a tutelle + every delegated party.
        supabase
          .from("entities")
          .select("*", { count: "exact", head: true })
          .or("parent_siren.not.is.null,level.eq.delegated"),
        supabase.from("contracts").select("*", { count: "exact", head: true }),
        supabase
          .from("edges")
          .select("source_siren,target_siren,type,amount_eur,exercice")
          .or(teaserScope),
      ]);
      if (cancelled) return;

      if (
        budgetRes.error ||
        instRes.error ||
        opRes.error ||
        contractRes.error ||
        teaserEdgeRes.error
      ) {
        console.error("Overview load failed", {
          budget: budgetRes.error,
          institutions: instRes.error,
          operateurs: opRes.error,
          contract: contractRes.error,
          teaser: teaserEdgeRes.error,
        });
        setState({ status: "error" });
        return;
      }

      const budget = (budgetRes.data as BudgetRow[] | null) ?? [];
      const teaserEdges = (teaserEdgeRes.data as FlowEdge[] | null) ?? [];

      const figures: OverviewFigures = {
        // Voted State credits only: pin the LOLF universe so a future voted non-LOLF fact (local
        // M57 / social LFSS) can never leak into the State CP headline (anti-double-counting).
        budgetCp: budget
          .filter((b) => b.nomenclature === "lolf" && !b.executed && b.exercice === BUDGET_EXERCICE)
          .reduce((sum, b) => sum + (b.amount_cp_eur ?? 0), 0),
        institutions: instRes.count ?? 0,
        operateurs: opRes.count ?? 0,
        contrats: contractRes.count ?? 0,
      };

      // Names for the teaser ministry + its scoped neighbours (bounded by the scoped edge set).
      const sirens = new Set<string>([TEASER_MINISTRY]);
      for (const e of teaserEdges) {
        sirens.add(e.source_siren);
        sirens.add(e.target_siren);
      }
      const nameRes = await supabase
        .from("entities")
        .select("siren,name,level")
        .in("siren", [...sirens]);
      if (cancelled) return;
      if (nameRes.error) {
        // The teaser is a secondary signal; degrade to an empty teaser (logged) rather than blank
        // the whole landing page — the headline figures above are the main content and have loaded.
        console.error("Overview teaser names load failed (teaser hidden)", nameRes.error);
      }

      const entityBySiren = new Map<string, FlowEntity>(
        ((nameRes.data as FlowEntity[] | null) ?? []).map((e) => [e.siren, e]),
      );

      setState({
        status: "ready",
        figures,
        teaser: {
          name: entityBySiren.get(TEASER_MINISTRY)?.name ?? "",
          links: buildFlowLinks(TEASER_MINISTRY, teaserEdges, entityBySiren),
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
