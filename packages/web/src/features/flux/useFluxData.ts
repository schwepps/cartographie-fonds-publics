import { useEffect, useState } from "react";
import { supabase } from "../../lib/supabase";
import type { FlowEdge, FlowEntity } from "../../lib/flows";

interface EntityRow {
  siren: string;
  name: string;
  level: string | null;
  category: string | null;
}

export interface FluxModel {
  entityBySiren: Map<string, FlowEntity>;
  edges: FlowEdge[];
  ministries: { siren: string; name: string }[];
}

export type FluxState =
  | { status: "loading" }
  | { status: "error" }
  | { status: "ready"; model: FluxModel };

/**
 * Loads the entities + edges needed to build funding-flow Sankey links (financeur → opérateur →
 * titulaire). The curated graph is small, so it fetches both in full and the page builds the links
 * client-side for the selected root ministry. Reads go through PostgREST under RLS.
 */
export function useFluxData(): FluxState {
  const [state, setState] = useState<FluxState>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;

    async function load() {
      const [entityRes, edgeRes] = await Promise.all([
        supabase.from("entities").select("siren,name,level,category").limit(5000),
        supabase
          .from("edges")
          .select("source_siren,target_siren,type,amount_eur,exercice")
          .limit(20000),
      ]);
      if (cancelled) return;
      if (entityRes.error || edgeRes.error) {
        console.error("Flux load failed", { entity: entityRes.error, edge: edgeRes.error });
        setState({ status: "error" });
        return;
      }
      const entities = (entityRes.data as EntityRow[] | null) ?? [];
      const edges = (edgeRes.data as FlowEdge[] | null) ?? [];
      const entityBySiren = new Map<string, FlowEntity>(
        entities.map((e) => [e.siren, { siren: e.siren, name: e.name, level: e.level }]),
      );
      const ministries = entities
        .filter((e) => e.category === "ministère")
        .map((e) => ({ siren: e.siren, name: e.name }));

      setState({ status: "ready", model: { entityBySiren, edges, ministries } });
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  return state;
}
