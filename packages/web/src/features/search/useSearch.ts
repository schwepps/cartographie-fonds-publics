import { useEffect, useState } from "react";
import { supabase } from "../../lib/supabase";
import { acronymOf } from "../../lib/acronyms";
import { buildMagnitudeMap, type AmountEdge } from "../../lib/magnitude";

export interface SearchEntity {
  siren: string;
  name: string;
  level: string | null;
  category: string | null;
  parent_siren: string | null;
  acronym: string | null;
  /** Derived CP magnitude (budget / funds) — drives the amount column + sort. */
  magnitude: number;
}

interface BudgetRow {
  entity_siren: string | null;
  exercice: number;
  amount_cp_eur: number | null;
  executed: boolean;
}

export type SearchState =
  | { status: "loading" }
  | { status: "error" }
  | {
      status: "ready";
      entities: SearchEntity[];
      bySiren: Map<string, SearchEntity>;
      ministries: SearchEntity[];
    };

/** Sum of voted CP for each entity's latest exercice — the budget side of an entity's magnitude. */
function budgetCpBySiren(budget: BudgetRow[]): Map<string, number> {
  const latest = new Map<string, number>(); // siren → latest voted exercice
  for (const row of budget) {
    if (row.executed || row.entity_siren == null) continue;
    latest.set(row.entity_siren, Math.max(latest.get(row.entity_siren) ?? 0, row.exercice));
  }
  const cp = new Map<string, number>();
  for (const row of budget) {
    if (row.executed || row.entity_siren == null) continue;
    if (row.exercice !== latest.get(row.entity_siren)) continue;
    cp.set(row.entity_siren, (cp.get(row.entity_siren) ?? 0) + (row.amount_cp_eur ?? 0));
  }
  return cp;
}

/**
 * Loads the searchable institution set: all entities + the edges/budget needed to derive each
 * entity's CP magnitude. The set is small (seed/demo scale), so search/facet filtering happens
 * client-side in the page; production scale would move to a server-side RPC.
 */
export function useSearch(): SearchState {
  const [state, setState] = useState<SearchState>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;

    async function load() {
      const [entityRes, edgeRes, budgetRes] = await Promise.all([
        supabase.from("entities").select("siren,name,level,category,parent_siren").limit(5000),
        supabase.from("edges").select("source_siren,target_siren,type,amount_eur").limit(20000),
        supabase.from("budget_facts").select("entity_siren,exercice,amount_cp_eur,executed"),
      ]);
      if (cancelled) return;

      if (entityRes.error || edgeRes.error || budgetRes.error) {
        console.error("Search load failed", {
          entity: entityRes.error,
          edge: edgeRes.error,
          budget: budgetRes.error,
        });
        setState({ status: "error" });
        return;
      }

      const rawEntities =
        (entityRes.data as Omit<SearchEntity, "acronym" | "magnitude">[] | null) ?? [];
      const edges = (edgeRes.data as AmountEdge[] | null) ?? [];
      const budget = (budgetRes.data as BudgetRow[] | null) ?? [];

      const magnitude = buildMagnitudeMap(edges, budgetCpBySiren(budget));
      const entities: SearchEntity[] = rawEntities.map((e) => ({
        ...e,
        acronym: acronymOf(e.siren),
        magnitude: magnitude.get(e.siren) ?? 0,
      }));
      const bySiren = new Map(entities.map((e) => [e.siren, e]));
      const ministries = entities.filter((e) => e.category === "ministère");

      setState({ status: "ready", entities, bySiren, ministries });
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  return state;
}
