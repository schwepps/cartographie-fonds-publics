import type { ReactNode } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import Sigma from "sigma";
import { DataTableFallback } from "../../lib/a11y/DataTableFallback";
import { buildGraph, edgeKey } from "./graph-model";
import { NODE_LIMIT, useGraphData } from "./useGraphData";

/**
 * Institutional graph explorer — pan/zoom the network (Sigma.js) and expand a node's neighbourhood
 * via the depth-capped `graph_neighbors` RPC. Clicking a node selects it and loads its neighbours;
 * the selected-node aside and the accessible `DataTableFallback` both link through to the entity
 * sheet. The canvas is `aria-hidden` (a decorative duplicate); the table is the non-visual
 * equivalent the web-shell convention requires every graphical view to provide, and the keyboard
 * path to each sheet. Sigma needs WebGL, so its init is guarded — under jsdom (tests) it no-ops and
 * the page still renders the table.
 */
export default function GraphPage() {
  const { t, i18n } = useTranslation();
  const { state, expand } = useGraphData();
  const containerRef = useRef<HTMLDivElement>(null);
  const [selected, setSelected] = useState<string | null>(null);

  // Key the graph on the node/edge arrays only (not the whole state): toggling `expandError` or
  // `truncated` must not rebuild Sigma. `mergeNeighbourRows` preserves array identity when nothing
  // changed, so an idempotent expand on the seed leaves the renderer untouched.
  const nodes = state.status === "ready" ? state.nodes : null;
  const edges = state.status === "ready" ? state.edges : null;
  const graph = useMemo(() => (nodes && edges ? buildGraph(nodes, edges) : null), [nodes, edges]);

  useEffect(() => {
    if (!graph || !containerRef.current) return;
    let renderer: Sigma | null = null;
    try {
      renderer = new Sigma(graph, containerRef.current, { renderEdgeLabels: true });
      renderer.on("clickNode", ({ node }) => {
        setSelected(node);
        void expand(node);
      });
    } catch {
      // WebGL/canvas unavailable (jsdom under test, or an unsupported browser): degrade to the
      // accessible table below rather than crashing the page.
      renderer?.kill();
      return;
    }
    return () => renderer?.kill();
  }, [graph, expand]);

  if (state.status === "loading") {
    return (
      <section className="fr-container legacy-page">
        <h1 className="fr-h1">{t("graph.title")}</h1>
        <p className="fr-lead">{t("graph.loading")}</p>
      </section>
    );
  }
  if (state.status === "error") {
    return (
      <section className="fr-container legacy-page">
        <h1 className="fr-h1">{t("graph.title")}</h1>
        <p role="alert" className="text-error">
          {t("graph.error")}
        </p>
      </section>
    );
  }

  const selectedNode = state.nodes.find((node) => node.siren === selected);
  const nameBySiren = new Map(state.nodes.map((node) => [node.siren, node.name]));
  const nameOf = (siren: string): string => nameBySiren.get(siren) ?? siren;

  const nodeColumns = [
    { key: "name", header: t("graph.col.name") },
    { key: "level", header: t("graph.col.level") },
    { key: "category", header: t("graph.col.category") },
  ];
  // Sort in the active UI language; carry `siren` so rows key stably (nodes re-sort as expand adds).
  const nodeRows: Array<Record<string, ReactNode>> = [...state.nodes]
    .sort((a, b) => a.name.localeCompare(b.name, i18n.language))
    .map((node) => ({
      siren: node.siren,
      name: <Link to={`/entity/${node.siren}`}>{node.name}</Link>,
      level: node.level ?? "—",
      category: node.category ?? "—",
    }));

  // The graph's primary information is its connectivity — surface the edges as an accessible table
  // too, so non-visual users reach the relationships, not just the node list.
  const relColumns = [
    { key: "source", header: t("graph.relCol.source") },
    { key: "type", header: t("graph.relCol.type") },
    { key: "target", header: t("graph.relCol.target") },
  ];
  const relRows: Array<Record<string, ReactNode>> = state.edges.map((edge) => ({
    relKey: edgeKey(edge.source_siren, edge.target_siren, edge.type),
    source: <Link to={`/entity/${edge.source_siren}`}>{nameOf(edge.source_siren)}</Link>,
    type: edge.type,
    target: <Link to={`/entity/${edge.target_siren}`}>{nameOf(edge.target_siren)}</Link>,
  }));

  return (
    <section className="fr-container legacy-page">
      <h1 className="fr-h1">{t("graph.title")}</h1>
      <p className="fr-sm">{t("graph.expandHint")}</p>
      {state.truncated ? (
        <p className="fr-sm">{t("graph.limitNotice", { limit: NODE_LIMIT })}</p>
      ) : null}
      {state.expandError ? (
        <p role="alert" className="text-error fr-sm">
          {t("graph.expandError")}
        </p>
      ) : null}

      <div
        ref={containerRef}
        aria-hidden="true"
        style={{ width: "100%", height: "min(60vh, 480px)" }}
      />

      {selectedNode ? (
        <aside
          className="stack"
          style={{ marginTop: "var(--sp-5)" }}
          aria-label={t("graph.selectedLabel")}
        >
          <p className="text-bold">{selectedNode.name}</p>
          <Link className="fr-link" to={`/entity/${selectedNode.siren}`}>
            {t("graph.openSheet")}
          </Link>
        </aside>
      ) : null}

      <h2 className="fr-h2">{t("graph.fallbackTitle")}</h2>
      {state.nodes.length === 0 ? (
        <p>{t("graph.empty")}</p>
      ) : (
        <DataTableFallback
          caption={t("graph.fallbackCaption")}
          columns={nodeColumns}
          rows={nodeRows}
          getRowKey={(row) => String(row.siren)}
        />
      )}

      <h2 className="fr-h2">{t("graph.relTitle")}</h2>
      {state.edges.length === 0 ? (
        <p>{t("graph.relEmpty")}</p>
      ) : (
        <DataTableFallback
          caption={t("graph.relCaption")}
          columns={relColumns}
          rows={relRows}
          getRowKey={(row) => String(row.relKey)}
        />
      )}
    </section>
  );
}
