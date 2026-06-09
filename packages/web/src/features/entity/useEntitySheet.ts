import { useEffect, useState } from "react";
import { supabase } from "../../lib/supabase";
import { isSiren } from "../../lib/siren";
import type { BudgetFactRow, EdgeRow, EntityRow } from "./types";

export type EntitySheetState =
  | { status: "loading" }
  | { status: "error" }
  | {
      status: "ready";
      entity: EntityRow | null;
      edges: EdgeRow[];
      budgetFacts: BudgetFactRow[];
      /** SIREN → name for the entity's tutelle + relationship counterparts (readable labels). */
      nameBySiren: Map<string, string>;
    };

const EMPTY_READY: EntitySheetState = {
  status: "ready",
  entity: null,
  edges: [],
  budgetFacts: [],
  nameBySiren: new Map(),
};

/** The entity on the other end of an edge from `siren`'s perspective. */
export function counterpartSiren(edge: EdgeRow, siren: string): string {
  return edge.source_siren === siren ? edge.target_siren : edge.source_siren;
}

/**
 * Loads an entity, the edges it participates in (as source or target), and its budget facts
 * (PLF/LFI mission/programme figures attributed to it) from Supabase via PostgREST. A second
 * round resolves the names of the entity's tutelle + relationship counterparts so the sheet reads
 * in plain language rather than bare SIRENs. `edges` carry `provenance` + `exercice`, so the sheet
 * renders provenance per relationship without an extra join.
 */
export function useEntitySheet(siren: string): EntitySheetState {
  const [state, setState] = useState<EntitySheetState>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;

    async function load() {
      // Validate the URL param before it reaches a query. Beyond being a not-found short-circuit,
      // this stops the raw `:siren` from being interpolated into the PostgREST `.or(...)` filter
      // string below (filter injection at a trust boundary).
      if (!isSiren(siren)) {
        setState(EMPTY_READY);
        return;
      }
      setState({ status: "loading" });
      const [entityRes, edgesRes, budgetRes] = await Promise.all([
        supabase
          .from("entities")
          .select("siren,name,level,category,parent_siren,provenance")
          .eq("siren", siren)
          .maybeSingle(),
        supabase
          .from("edges")
          .select("source_siren,target_siren,type,amount_eur,exercice,provenance")
          .or(`source_siren.eq.${siren},target_siren.eq.${siren}`),
        supabase
          .from("budget_facts")
          .select("exercice,mission,programme,amount_ae_eur,amount_cp_eur,executed")
          .eq("entity_siren", siren),
      ]);

      if (cancelled) return;
      if (entityRes.error || edgesRes.error || budgetRes.error) {
        console.error(
          "Entity sheet load failed",
          entityRes.error ?? edgesRes.error ?? budgetRes.error,
        );
        setState({ status: "error" });
        return;
      }

      const entity = (entityRes.data as EntityRow | null) ?? null;
      const edges = (edgesRes.data as EdgeRow[] | null) ?? [];
      const budgetFacts = (budgetRes.data as BudgetFactRow[] | null) ?? [];

      // Resolve the names of every SIREN the sheet links to: the tutelle parent + each relationship
      // counterpart. These SIRENs are trusted DB values (not user input), so a single `.in(...)`
      // batch is safe and avoids N round-trips.
      const relatedSirens = new Set<string>();
      if (entity?.parent_siren) relatedSirens.add(entity.parent_siren);
      for (const edge of edges) relatedSirens.add(counterpartSiren(edge, siren));

      const nameBySiren = new Map<string, string>();
      if (relatedSirens.size > 0) {
        const namesRes = await supabase
          .from("entities")
          .select("siren,name")
          .in("siren", [...relatedSirens]);
        if (cancelled) return;
        if (namesRes.error) {
          console.error("Entity name lookup failed", namesRes.error);
          setState({ status: "error" });
          return;
        }
        for (const row of (namesRes.data as Array<Pick<EntityRow, "siren" | "name">> | null) ??
          []) {
          nameBySiren.set(row.siren, row.name);
        }
      }

      setState({ status: "ready", entity, edges, budgetFacts, nameBySiren });
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [siren]);

  return state;
}
