import { useEffect, useState } from "react";
import { supabase } from "../../lib/supabase";
import { buildFlowLinks, type FlowEdge, type FlowEntity, type SankeyLink } from "../../lib/flows";
import type { Level } from "../../lib/levels";

/** Ministry whose funding flows seed the perimeter teaser (ESR — the richest funds cluster). */
const TEASER_MINISTRY = "110044013";

/** Exercice the State headline sums (voted LFI), kept consistent with the Home overview. */
const STATE_EXERCICE = 2025;

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
  nomenclature: string | null;
}
interface ContractRow {
  montant_eur: number | null;
  exercice: number | null;
}

/** One headline per administrative level, with the source that backs it (for the provenance badge). */
export interface PerimetreFigure {
  level: Level;
  /** Headline amount in euros (a per-level order of magnitude — never a cross-level sum). */
  total: number;
  /** Registry source id stamped on the contributing rows, resolved by the provenance UI. */
  provenanceId: string;
  /** Exercice the figure sums (its single-year order of magnitude), or null if no dated rows. */
  millesime: number | null;
  /** Existing route this level's detail lives on. */
  detailTo: string;
}

export type PerimetreState =
  | { status: "loading" }
  | { status: "error" }
  | {
      status: "ready";
      figures: PerimetreFigure[];
      teaser: { name: string; links: SankeyLink[] };
    };

/** Max exercice among a set of rows, else null. */
function latestExercice(exercices: Array<number | null>): number | null {
  const years = exercices.filter((y): y is number => y != null);
  return years.length ? Math.max(...years) : null;
}

/**
 * Sum a level's rows for its latest exercice only, returning that exercice as the badge millésime.
 * Keeping the total and the badge on the same single year avoids a silent cross-year sum presented
 * under a one-year label (each headline is a per-sphere order of magnitude, not a multi-year total).
 */
function latestYearTotal<T>(
  rows: T[],
  getYear: (row: T) => number | null,
  getAmount: (row: T) => number | null,
): { total: number; millesime: number | null } {
  const millesime = latestExercice(rows.map(getYear));
  const inYear = millesime == null ? rows : rows.filter((row) => getYear(row) === millesime);
  return { total: inYear.reduce((s, row) => s + (getAmount(row) ?? 0), 0), millesime };
}

/**
 * Whole-perimeter overview data: one headline figure per level (State / local / social / delegated),
 * each computed in its OWN accounting universe so they are never silently summed. State = voted LOLF
 * credits (mirrors Home), local = M57/M14 balances, social = the aggregated LFSS module, delegated =
 * public-contract amounts. The curated graph is small (seed scale), so it fetches the tables in full
 * and aggregates client-side — all reads straight through PostgREST under RLS.
 */
export function usePerimetreData(): PerimetreState {
  const [state, setState] = useState<PerimetreState>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;

    async function load() {
      const [entityRes, edgeRes, budgetRes, contractRes] = await Promise.all([
        supabase.from("entities").select("siren,name,level,parent_siren"),
        supabase.from("edges").select("source_siren,target_siren,type,amount_eur,exercice"),
        supabase.from("budget_facts").select("exercice,amount_cp_eur,executed,nomenclature"),
        supabase.from("contracts").select("montant_eur,exercice"),
      ]);
      if (cancelled) return;

      if (entityRes.error || edgeRes.error || budgetRes.error || contractRes.error) {
        console.error("Perimetre load failed", {
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
      const contracts = (contractRes.data as ContractRow[] | null) ?? [];

      // State: voted LOLF credits for the headline exercice (the anti-double-counting universe of
      // the State budget) — the same basis the Home figure uses; total and badge share STATE_EXERCICE.
      const stateTotal = budget
        .filter((b) => b.nomenclature === "lolf" && !b.executed && b.exercice === STATE_EXERCICE)
        .reduce((s, b) => s + (b.amount_cp_eur ?? 0), 0);
      // Local: M57/M14 balances (cash basis, realised); social: the aggregated LFSS module by branche;
      // delegated: public-contract amounts (recipients, not a budget universe). These universes carry
      // realised facts, so filter on `executed` (symmetric with the State `!executed` voted filter) —
      // a future voted M57/M14/LFSS row never leaks in. Each is summed for its latest exercice only,
      // so the headline and its millésime badge stay on one year.
      const local = latestYearTotal(
        budget.filter((b) => b.executed && (b.nomenclature === "m57" || b.nomenclature === "m14")),
        (b) => b.exercice,
        (b) => b.amount_cp_eur,
      );
      const social = latestYearTotal(
        budget.filter((b) => b.executed && b.nomenclature === "social"),
        (b) => b.exercice,
        (b) => b.amount_cp_eur,
      );
      const delegated = latestYearTotal(
        contracts,
        (c) => c.exercice,
        (c) => c.montant_eur,
      );

      const figures: PerimetreFigure[] = [
        {
          level: "state",
          total: stateTotal,
          provenanceId: "budget_plf_lfi",
          millesime: STATE_EXERCICE,
          detailTo: "/graph",
        },
        {
          level: "local",
          total: local.total,
          provenanceId: "finances_locales_ofgl",
          millesime: local.millesime,
          detailTo: "/flux",
        },
        {
          level: "social",
          total: social.total,
          provenanceId: "comptes_sociaux",
          millesime: social.millesime,
          detailTo: "/sources#source-comptes_sociaux",
        },
        {
          level: "delegated",
          total: delegated.total,
          provenanceId: "decp_commande_publique",
          millesime: delegated.millesime,
          detailTo: "/flux",
        },
      ];

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
