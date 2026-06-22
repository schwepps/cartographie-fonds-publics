import { useEffect, useState } from "react";
import { supabase } from "../../lib/supabase";
import type { FlowEdge, FlowEntity } from "../../lib/flows";

export interface Delegator {
  siren: string;
  name: string;
  level: string | null;
  total_eur: number | null;
  contracts: number;
}

export interface FluxModel {
  /** Focus options: the top public buyers by delegated amount (Sankey roots). */
  delegators: Delegator[];
  /** The focused buyer's top `delegates` edges (scoped), ready for buildFlowLinks. */
  edges: FlowEdge[];
  entityBySiren: Map<string, FlowEntity>;
  /** The resolved focus (the selection, or the top delegator by default). */
  focusSiren: string | null;
}

export type FluxState =
  | { status: "loading" }
  | { status: "error" }
  | { status: "ready"; model: FluxModel };

/** How many of a buyer's largest delegations the Sankey shows (a buyer can have thousands). */
const TOP_FLOWS = 40;

/**
 * Funding-flow data for the Flux Sankey. The financeur→opérateur (`funds`) layer has no open-data
 * source yet, so this surfaces the real money the graph does carry: `delegates` edges (public buyer
 * → DECP supplier). The selector lists the top buyers by delegated amount (`top_delegators` RPC,
 * migration 0010); the chosen buyer's largest delegations are fetched **scoped** (not the whole
 * ~1.2M-edge graph) and fed to `buildFlowLinks`. Re-runs whenever `focusSiren` changes.
 */
export function useFluxData(focusSiren: string | null): FluxState {
  const [state, setState] = useState<FluxState>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;

    async function load() {
      const delRes = await supabase.rpc("top_delegators", { p_limit: 40 });
      if (cancelled) return;
      if (delRes.error) {
        console.error("Flux delegators load failed", delRes.error);
        setState({ status: "error" });
        return;
      }
      const delegators = (delRes.data as Delegator[] | null) ?? [];
      const focus = focusSiren ?? delegators[0]?.siren ?? null;

      let edges: FlowEdge[] = [];
      const entityBySiren = new Map<string, FlowEntity>();
      if (focus) {
        const edgeRes = await supabase
          .from("edges")
          .select("source_siren,target_siren,type,amount_eur,exercice")
          .eq("source_siren", focus)
          .eq("type", "delegates")
          .order("amount_eur", { ascending: false, nullsFirst: false })
          .limit(TOP_FLOWS);
        if (cancelled) return;
        if (edgeRes.error) {
          console.error("Flux edges load failed", edgeRes.error);
          setState({ status: "error" });
          return;
        }
        edges = (edgeRes.data as FlowEdge[] | null) ?? [];
        const sirens = new Set<string>([focus]);
        for (const e of edges) sirens.add(e.target_siren);
        const entRes = await supabase
          .from("entities")
          .select("siren,name,level")
          .in("siren", [...sirens]);
        if (cancelled) return;
        if (entRes.error) {
          // The entity names label every Sankey node/link, so a failure here is not recoverable —
          // surface the error rather than render unlabeled flows.
          console.error("Flux entities load failed", entRes.error);
          setState({ status: "error" });
          return;
        }
        for (const e of (entRes.data as FlowEntity[] | null) ?? []) entityBySiren.set(e.siren, e);
        // Ensure the focus is labelled even if it is an unresolved buyer (use the delegator record).
        if (!entityBySiren.has(focus)) {
          const d = delegators.find((x) => x.siren === focus);
          if (d) entityBySiren.set(focus, { siren: d.siren, name: d.name, level: d.level });
        }
      }

      setState({
        status: "ready",
        model: { delegators, edges, entityBySiren, focusSiren: focus },
      });
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [focusSiren]);

  return state;
}
