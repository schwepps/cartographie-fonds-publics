import type { ReactNode } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import Sigma from "sigma";
import { DataTableFallback } from "../../lib/a11y/DataTableFallback";
import { buildGraph } from "./graph-model";
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
  const { t } = useTranslation();
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
      <section>
        <h1 className="fr-h1">{t("graph.title")}</h1>
        <p className="fr-text--lead">{t("graph.loading")}</p>
      </section>
    );
  }
  if (state.status === "error") {
    return (
      <section>
        <h1 className="fr-h1">{t("graph.title")}</h1>
        <p role="alert" className="fr-text-default--error">
          {t("graph.error")}
        </p>
      </section>
    );
  }

  const selectedNode = state.nodes.find((node) => node.siren === selected);
  const columns = [
    { key: "name", header: t("graph.col.name") },
    { key: "level", header: t("graph.col.level") },
    { key: "category", header: t("graph.col.category") },
  ];
  const rows: Array<Record<string, ReactNode>> = [...state.nodes]
    .sort((a, b) => a.name.localeCompare(b.name, "fr"))
    .map((node) => ({
      name: <Link to={`/entity/${node.siren}`}>{node.name}</Link>,
      level: node.level ?? "—",
      category: node.category ?? "—",
    }));

  return (
    <section>
      <h1 className="fr-h1">{t("graph.title")}</h1>
      <p className="fr-text--sm">{t("graph.expandHint")}</p>
      {state.truncated ? (
        <p className="fr-text--sm">{t("graph.limitNotice", { limit: NODE_LIMIT })}</p>
      ) : null}
      {state.expandError ? (
        <p role="alert" className="fr-text-default--error fr-text--sm">
          {t("graph.expandError")}
        </p>
      ) : null}

      <div
        ref={containerRef}
        aria-hidden="true"
        style={{ width: "100%", height: "min(60vh, 480px)" }}
      />

      {selectedNode ? (
        <aside className="fr-mt-2w" aria-label={t("graph.selectedLabel")}>
          <p className="fr-text--bold fr-mb-1v">{selectedNode.name}</p>
          <Link className="fr-link" to={`/entity/${selectedNode.siren}`}>
            {t("graph.openSheet")}
          </Link>
        </aside>
      ) : null}

      <h2 className="fr-h2">{t("graph.fallbackTitle")}</h2>
      {state.nodes.length === 0 ? (
        <p>{t("graph.empty")}</p>
      ) : (
        <DataTableFallback caption={t("graph.fallbackCaption")} columns={columns} rows={rows} />
      )}
    </section>
  );
}
