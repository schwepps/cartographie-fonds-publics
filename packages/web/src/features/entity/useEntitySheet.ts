import { useEffect, useState } from "react";
import { supabase } from "../../lib/supabase";
import type { EdgeRow, EntityRow } from "./types";

export type EntitySheetState =
  | { status: "loading" }
  | { status: "error" }
  | { status: "ready"; entity: EntityRow | null; edges: EdgeRow[] };

/** SIREN is exactly 9 digits — the canonical join key. */
const SIREN_RE = /^\d{9}$/;

/**
 * Loads an entity and the edges it participates in (as source or target) from
 * Supabase via PostgREST. `edges` already carry `provenance` and `exercice`, so the
 * sheet renders provenance per figure without an extra join or RPC change.
 */
export function useEntitySheet(siren: string): EntitySheetState {
  const [state, setState] = useState<EntitySheetState>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;

    async function load() {
      // Validate the URL param before it reaches a query. Beyond being a not-found
      // short-circuit, this stops the raw `:siren` from being interpolated into the
      // PostgREST `.or(...)` filter string below (filter injection at a trust boundary).
      if (!SIREN_RE.test(siren)) {
        setState({ status: "ready", entity: null, edges: [] });
        return;
      }
      setState({ status: "loading" });
      const [entityRes, edgesRes] = await Promise.all([
        supabase
          .from("entities")
          .select("siren,name,level,category,provenance")
          .eq("siren", siren)
          .maybeSingle(),
        supabase
          .from("edges")
          .select("source_siren,target_siren,type,amount_eur,exercice,provenance")
          .or(`source_siren.eq.${siren},target_siren.eq.${siren}`),
      ]);

      if (cancelled) return;
      if (entityRes.error || edgesRes.error) {
        setState({ status: "error" });
        return;
      }
      setState({
        status: "ready",
        entity: (entityRes.data as EntityRow | null) ?? null,
        edges: (edgesRes.data as EdgeRow[] | null) ?? [],
      });
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [siren]);

  return state;
}
