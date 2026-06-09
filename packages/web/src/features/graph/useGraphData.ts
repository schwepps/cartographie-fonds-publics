import { useCallback, useEffect, useState } from "react";
import { supabase } from "../../lib/supabase";
import { isSiren } from "../../lib/siren";
import { mergeNeighbourRows } from "./graph-model";
import type { GraphEdge, GraphNeighbourRow, GraphNode } from "./graph-model";

/**
 * Bounded initial fetch (Phase-1, seed scale). The full load (FSC-35) brings thousands of entities;
 * until a scalable viewport-driven load lands, we cap the seed network and surface the cap rather
 * than silently truncating it.
 */
export const NODE_LIMIT = 200;

export type GraphDataState =
  | { status: "loading" }
  | { status: "error" }
  | {
      status: "ready";
      nodes: GraphNode[];
      edges: GraphEdge[];
      truncated: boolean;
      /** Set when an expand() call failed, so the UI can show a non-fatal notice. */
      expandError: boolean;
    };

export interface UseGraphData {
  state: GraphDataState;
  /** Expand a node's neighbourhood via the `graph_neighbors` RPC, merging new nodes/edges in. */
  expand: (siren: string) => Promise<void>;
}

/**
 * Loads the seed institutional network (a bounded entities + edges fetch) and exposes an `expand`
 * action that calls the depth-capped `graph_neighbors` RPC and folds new neighbours into state.
 * Expansion is idempotent — on the tiny seed the neighbourhood is already present, so state keeps
 * its identity and no re-render churns. All reads go straight through PostgREST/RPC under RLS.
 */
export function useGraphData(): UseGraphData {
  const [state, setState] = useState<GraphDataState>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;

    async function load() {
      const [entityRes, edgeRes] = await Promise.all([
        supabase.from("entities").select("siren,name,level,category").limit(NODE_LIMIT),
        supabase.from("edges").select("source_siren,target_siren,type"),
      ]);
      if (cancelled) return;
      if (entityRes.error || edgeRes.error) {
        console.error("Graph initial load failed", entityRes.error ?? edgeRes.error);
        setState({ status: "error" });
        return;
      }
      const nodes = (entityRes.data as GraphNode[] | null) ?? [];
      const edges = (edgeRes.data as GraphEdge[] | null) ?? [];
      setState({
        status: "ready",
        nodes,
        edges,
        truncated: nodes.length >= NODE_LIMIT,
        expandError: false,
      });
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  const expand = useCallback(async (siren: string) => {
    if (!isSiren(siren)) return;

    // A failed expand must not look like "this node has no neighbours" — flag it so the UI can
    // show a non-fatal notice (never swallow the error silently).
    const flagExpandError = () =>
      setState((prev) => (prev.status === "ready" ? { ...prev, expandError: true } : prev));

    const { data, error } = await supabase.rpc("graph_neighbors", { p_siren: siren, p_depth: 1 });
    if (error || !data) {
      console.error("graph_neighbors RPC failed", error);
      flagExpandError();
      return;
    }
    const rows = data as GraphNeighbourRow[];

    // Resolve names/levels for every SIREN the traversal touched (one batch), so freshly added
    // nodes render with a label and the right colour.
    const sirens = [...new Set(rows.flatMap((row) => [row.source_siren, row.target_siren]))];
    let fetchedNodes: GraphNode[] = [];
    if (sirens.length > 0) {
      const namesRes = await supabase
        .from("entities")
        .select("siren,name,level,category")
        .in("siren", sirens);
      if (namesRes.error) {
        console.error("Graph neighbour name lookup failed", namesRes.error);
        flagExpandError();
        return;
      }
      fetchedNodes = (namesRes.data as GraphNode[] | null) ?? [];
    }

    setState((prev) => {
      if (prev.status !== "ready") return prev;
      const merged = mergeNeighbourRows(prev.nodes, prev.edges, rows, fetchedNodes);
      const unchanged = merged.nodes === prev.nodes && merged.edges === prev.edges;
      if (unchanged) {
        // Nothing new (idempotent on the seed); only re-render to clear a stale expand error.
        return prev.expandError ? { ...prev, expandError: false } : prev;
      }
      return { ...prev, nodes: merged.nodes, edges: merged.edges, expandError: false };
    });
  }, []);

  return { state, expand };
}
