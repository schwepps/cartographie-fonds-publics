import { useEffect, useState } from "react";
import { supabase } from "../../lib/supabase";
import { acronymOf } from "../../lib/acronyms";
import { MINISTRY_CATEGORY } from "../../lib/levels";
import { budgetCpBySiren, buildMagnitudeMap, type BudgetCpRow } from "../../lib/magnitude";

export interface SearchEntity {
  siren: string;
  name: string;
  level: string | null;
  category: string | null;
  parent_siren: string | null;
  acronym: string | null;
  /** Derived CP magnitude (budget) — drives the amount column + sort. */
  magnitude: number;
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

type RawEntity = Omit<SearchEntity, "acronym" | "magnitude">;

/** Cap on server-side text matches; the full perimeter is ~150k entities, so we never fetch it. */
const RESULT_LIMIT = 200;
/** Empty-query browse default: the institutional perimeter (state/local/social), not the suppliers. */
const BROWSE_LIMIT = 1000;

const ENTITY_COLS = "siren,name,level,category,parent_siren";

/**
 * Query-driven institution search. Text matching happens **server-side**: a non-empty query goes to
 * the `search_entities` RPC (accent-insensitive `unaccent` ilike on name + SIREN, migration 0009),
 * so a département/operator/supplier is found regardless of the ~150k total — and "hérault" matches
 * "HERAULT" (the old client-side filter only ever saw PostgREST's first 1000-row page and was
 * accent-sensitive). An empty query browses the institutional perimeter (state/local/social).
 * Magnitude is the per-entity voted budget CP only — the edge-derived funding magnitude would need
 * the full ~1.2M-edge graph and is empty on the curated data anyway. Re-runs whenever `query` changes.
 */
export function useSearch(query: string): SearchState {
  const [state, setState] = useState<SearchState>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;

    async function load() {
      // Keep the previous results visible while a new query loads (no blank flash on each keystroke);
      // the initial state is already "loading".
      const q = query.trim();
      const base = () => supabase.from("entities").select(ENTITY_COLS);
      const resultQuery = q
        ? supabase.rpc("search_entities", { p_query: q, p_limit: RESULT_LIMIT })
        : base().in("level", ["state", "local", "social"]).limit(BROWSE_LIMIT);

      const [resultRes, ministryRes, budgetRes] = await Promise.all([
        resultQuery,
        base().eq("category", MINISTRY_CATEGORY).limit(100),
        supabase.from("budget_facts").select("entity_siren,exercice,amount_cp_eur,executed"),
      ]);
      if (cancelled) return;

      if (resultRes.error || ministryRes.error || budgetRes.error) {
        console.error("Search load failed", {
          result: resultRes.error,
          ministry: ministryRes.error,
          budget: budgetRes.error,
        });
        setState({ status: "error" });
        return;
      }

      const budget = (budgetRes.data as BudgetCpRow[] | null) ?? [];
      const magnitude = buildMagnitudeMap([], budgetCpBySiren(budget));
      const decorate = (e: RawEntity): SearchEntity => ({
        ...e,
        acronym: acronymOf(e.siren),
        magnitude: magnitude.get(e.siren) ?? 0,
      });

      const entities = ((resultRes.data as RawEntity[] | null) ?? []).map(decorate);
      const ministries = ((ministryRes.data as RawEntity[] | null) ?? []).map(decorate);
      // bySiren covers results + ministries so a result's tutelle chain can resolve its parent.
      const bySiren = new Map<string, SearchEntity>(
        [...ministries, ...entities].map((e) => [e.siren, e]),
      );

      setState({ status: "ready", entities, bySiren, ministries });
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [query]);

  return state;
}
