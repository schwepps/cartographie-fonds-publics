import { useCallback, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { euroCompact } from "../../lib/format";
import { LEVELS } from "../../lib/levels";
import { mixesPerimeters } from "../../lib/perimeter";
import { tutelleChain } from "../../lib/tutelle";
import {
  Bars,
  Breadcrumb,
  Button,
  Callout,
  Chip,
  Close,
  DataTable,
  ExampleFlag,
  Filter,
  Graph as GraphIcon,
  Keyboard,
  Layers,
  LevelBadge,
  LevelShape,
  MethodologyNote,
  Minus,
  Plus,
  Reset,
  Search as SearchIcon,
  StateBlock,
  Table as TableIcon,
  Warning,
  type DataTableColumn,
} from "../../lib/ui";
import { GraphCanvas, type GraphApi } from "./GraphCanvas";
import {
  passFilter,
  type GraphEdge,
  type GraphFilters,
  type GraphModel,
  type GraphNode,
} from "./graph-model";
import { useGraphData } from "./useGraphData";

const MIN_AMOUNT_STEPS = [0, 10e6, 100e6, 1e9, 10e9];
const LINK_LABELS: Record<string, string> = {
  tutelle: "Tutelle",
  funds: "Financement",
  participation: "Participation",
  delegates: "Délégation",
};

const defaultFilters = (): GraphFilters => ({
  levels: { state: true, local: true, social: true, delegated: true },
  ministry: "all",
  minAmount: 0,
  linkTypes: { tutelle: true, funds: true, participation: true, delegates: true },
});

const prefersReducedMotion = () =>
  typeof window !== "undefined" &&
  !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

function GraphLegend() {
  return (
    <div className="legend">
      <h4>Niveau (forme + couleur)</h4>
      {Object.values(LEVELS).map((m) => (
        <div className="legend__row" key={m.id}>
          <span className="legend__swatch">
            <LevelShape level={m.id} size={13} />
          </span>
          {m.label} <span className="fr-xs text-mention">· {m.desc}</span>
        </div>
      ))}
      <h4 style={{ marginTop: 10 }}>Liens</h4>
      <div className="legend__row">
        <svg width="24" height="10" aria-hidden="true">
          <line x1="1" y1="5" x2="23" y2="5" stroke="#7a7a86" strokeWidth="2" />
        </svg>{" "}
        Tutelle
      </div>
      <div className="legend__row">
        <svg width="24" height="10" aria-hidden="true">
          <line x1="1" y1="5" x2="23" y2="5" stroke="#0072b2" strokeWidth="3.4" />
        </svg>{" "}
        Financement <span className="fr-xs text-mention">(épaisseur ∝ montant)</span>
      </div>
      <div className="legend__row">
        <svg width="24" height="10" aria-hidden="true">
          <line
            x1="1"
            y1="5"
            x2="23"
            y2="5"
            stroke="#cf7a00"
            strokeWidth="2"
            strokeDasharray="5 4"
          />
        </svg>{" "}
        Délégation
      </div>
      <div className="legend__row fr-xs text-mention" style={{ marginTop: 4 }}>
        Taille du nœud ∝ crédits de paiement (échelle log)
      </div>
    </div>
  );
}

function FiltersPanel({
  filters,
  setFilters,
  ministries,
  open,
}: {
  filters: GraphFilters;
  setFilters: (updater: (f: GraphFilters) => GraphFilters) => void;
  ministries: GraphNode[];
  open: boolean;
}) {
  const set = (patch: Partial<GraphFilters>) => setFilters((f) => ({ ...f, ...patch }));
  return (
    <div className={`graph-filters ${open ? "open" : ""}`}>
      <div className="stack">
        <div>
          <h4 className="fr-h4" style={{ fontSize: "0.9rem", marginBottom: 8 }}>
            Niveau
          </h4>
          {Object.values(LEVELS).map((m) => (
            <label className="check-row" key={m.id}>
              <input
                type="checkbox"
                checked={filters.levels[m.id]}
                onChange={(e) => set({ levels: { ...filters.levels, [m.id]: e.target.checked } })}
              />
              <LevelShape level={m.id} size={11} /> {m.label}
            </label>
          ))}
        </div>
        <div className="field">
          <label className="field__label" htmlFor="f-min">
            Tutelle (ministère)
          </label>
          <select
            id="f-min"
            className="select"
            value={filters.ministry}
            onChange={(e) => set({ ministry: e.target.value })}
          >
            <option value="all">Toutes les tutelles</option>
            {ministries.map((m) => (
              <option key={m.siren} value={m.siren}>
                {m.acronym ?? m.name}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label className="field__label" htmlFor="f-amt">
            Montant minimum (CP) :{" "}
            <strong>{filters.minAmount === 0 ? "tous" : euroCompact(filters.minAmount)}</strong>
          </label>
          <input
            id="f-amt"
            type="range"
            min="0"
            max={MIN_AMOUNT_STEPS.length - 1}
            step="1"
            value={MIN_AMOUNT_STEPS.indexOf(filters.minAmount)}
            onChange={(e) => set({ minAmount: MIN_AMOUNT_STEPS[Number(e.target.value)] })}
            style={{ accentColor: "var(--blue-france)" }}
          />
          <span className="field__hint">Les ministères restent toujours affichés.</span>
        </div>
        <div>
          <h4 className="fr-h4" style={{ fontSize: "0.9rem", marginBottom: 8 }}>
            Type de lien
          </h4>
          {Object.entries(LINK_LABELS).map(([key, label]) => (
            <label className="check-row" key={key}>
              <input
                type="checkbox"
                checked={filters.linkTypes[key]}
                onChange={(e) =>
                  set({ linkTypes: { ...filters.linkTypes, [key]: e.target.checked } })
                }
              />
              {label}
            </label>
          ))}
        </div>
      </div>
    </div>
  );
}

function EntityPanel({
  siren,
  model,
  expanded,
  onClose,
  onOpenSheet,
  onExpand,
  onLocate,
}: {
  siren: string | null;
  model: GraphModel;
  expanded: Set<string>;
  onClose: () => void;
  onOpenSheet: (s: string) => void;
  onExpand: (s: string) => void;
  onLocate: (s: string) => void;
}) {
  if (!siren) return null;
  const e = model.byId.get(siren);
  if (!e) return null;
  const chain = tutelleChain(siren, model.byId);
  const children = model.nodes.filter((n) => n.parent_siren === siren);
  const out = model.edges
    .filter(
      (x) =>
        x.source_siren === siren && (x.type === "funds" || x.type === "delegates") && x.amount_eur,
    )
    .sort((a, b) => (b.amount_eur ?? 0) - (a.amount_eur ?? 0))
    .slice(0, 4);
  const max = out[0]?.amount_eur ?? 1;
  const canExpand =
    !expanded.has(siren) &&
    model.edges.some((x) => x.source_siren === siren || x.target_siren === siren);

  return (
    <aside className="entity-panel open" aria-label={`Résumé : ${e.name}`}>
      <Button
        variant="tertiary"
        iconOnly
        className="panel-close"
        aria-label="Fermer le panneau"
        onClick={onClose}
      >
        <Close />
      </Button>
      <div className="entity-panel__head">
        <div style={{ marginBottom: 10 }}>
          <LevelBadge level={e.level} unresolved={!e.resolved} />
        </div>
        <h2 className="fr-h3" style={{ marginBottom: 6 }}>
          {e.name}
        </h2>
        <nav className="breadcrumb" aria-label="Chaîne de tutelle">
          {chain.map((c, i) => (
            <span key={c.siren}>
              {i > 0 ? <span className="breadcrumb__sep">›</span> : null}
              {c.siren === siren ? (
                <span>{c.acronym ?? c.name}</span>
              ) : (
                <button type="button" className="fr-link" onClick={() => onLocate(c.siren)}>
                  {c.acronym ?? c.name}
                </button>
              )}
            </span>
          ))}
        </nav>
      </div>
      <div className="entity-panel__body stack">
        <div>
          <div
            className="fr-xs text-mention"
            style={{ textTransform: "uppercase", letterSpacing: ".04em", marginBottom: 4 }}
          >
            Crédits de paiement (CP) — exemple
          </div>
          <div className="figure__value" style={{ fontSize: "1.6rem" }}>
            {euroCompact(e.cp || null)}
          </div>
        </div>
        <dl className="kv">
          <dt>SIREN</dt>
          <dd>
            {e.resolved ? (
              <span className="mono">{e.siren}</span>
            ) : (
              <span className="text-mention">non résolu</span>
            )}
          </dd>
          <dt>Catégorie</dt>
          <dd>{e.category ?? "—"}</dd>
          <dt>Tutelle</dt>
          <dd>{e.parent_siren ? (model.byId.get(e.parent_siren)?.name ?? e.parent_siren) : "—"}</dd>
        </dl>
        {children.length ? (
          <div>
            <div className="fr-sm" style={{ fontWeight: 600, marginBottom: 6 }}>
              Opérateurs sous tutelle ({children.length})
            </div>
            <div className="row wrap" style={{ gap: 6 }}>
              {children.slice(0, 6).map((c) => (
                <Chip key={c.siren} small level={c.level} onClick={() => onLocate(c.siren)}>
                  {c.acronym ?? c.name.split(" ").slice(0, 3).join(" ")}
                </Chip>
              ))}
              {children.length > 6 ? (
                <span className="tag tag--sm">+{children.length - 6}</span>
              ) : null}
            </div>
          </div>
        ) : null}
        {out.length ? (
          <div>
            <div className="fr-sm" style={{ fontWeight: 600, marginBottom: 6 }}>
              Où va son argent (top {out.length})
            </div>
            <Bars
              items={out.map((o) => ({
                label: (model.byId.get(o.target_siren)?.name ?? o.target_siren)
                  .split(" ")
                  .slice(0, 4)
                  .join(" "),
                value: o.amount_eur ?? 0,
                amount: euroCompact(o.amount_eur),
                color: o.type === "delegates" ? "var(--niv-delegue)" : "var(--seq-5)",
              }))}
              max={max}
            />
          </div>
        ) : null}
      </div>
      <div className="entity-panel__foot">
        {canExpand ? (
          <Button variant="secondary" size="sm" onClick={() => onExpand(siren)}>
            <Plus /> Déplier
          </Button>
        ) : null}
        <Button
          variant="primary"
          size="sm"
          onClick={() => onOpenSheet(siren)}
          style={{ marginLeft: "auto" }}
        >
          Ouvrir la fiche
        </Button>
      </div>
    </aside>
  );
}

function GraphTableView({ model, filters }: { model: GraphModel; filters: GraphFilters }) {
  const nodes = model.nodes.filter((n) => passFilter(n, filters, model.byId));
  const visSet = new Set(nodes.map((n) => n.siren));
  const rels = model.edges.filter(
    (e) =>
      filters.linkTypes[e.type] !== false &&
      visSet.has(e.source_siren) &&
      visSet.has(e.target_siren),
  );
  const nameOf = (s: string) => model.byId.get(s)?.name ?? s;

  const nodeCols: DataTableColumn<GraphNode>[] = [
    {
      key: "name",
      header: "Institution",
      render: (r) => (
        <Link className="fr-link" to={`/entity/${r.siren}`}>
          {r.name}
        </Link>
      ),
      sortValue: (r) => r.name,
    },
    {
      key: "level",
      header: "Niveau",
      render: (r) => <LevelBadge level={r.level} unresolved={!r.resolved} />,
      sortValue: (r) => r.level ?? "",
    },
    { key: "category", header: "Catégorie", render: (r) => r.category ?? "—" },
    {
      key: "cp",
      header: "CP (exemple)",
      num: true,
      render: (r) => <span className="tnum">{euroCompact(r.cp || null)}</span>,
      sortValue: (r) => r.cp,
    },
  ];
  const relCols: DataTableColumn<GraphEdge>[] = [
    {
      key: "source",
      header: "Source",
      render: (r) => (
        <Link className="fr-link" to={`/entity/${r.source_siren}`}>
          {nameOf(r.source_siren)}
        </Link>
      ),
      sortValue: (r) => nameOf(r.source_siren),
    },
    {
      key: "type",
      header: "Relation",
      render: (r) => <span className="tag tag--sm">{LINK_LABELS[r.type] ?? r.type}</span>,
    },
    {
      key: "target",
      header: "Cible",
      render: (r) => (
        <Link className="fr-link" to={`/entity/${r.target_siren}`}>
          {nameOf(r.target_siren)}
        </Link>
      ),
      sortValue: (r) => nameOf(r.target_siren),
    },
    {
      key: "amount",
      header: "Montant",
      num: true,
      render: (r) => <span className="tnum">{euroCompact(r.amount_eur)}</span>,
      sortValue: (r) => r.amount_eur ?? 0,
    },
    { key: "exercice", header: "Millésime", num: true, render: (r) => r.exercice ?? "—" },
  ];

  // CP totals here span whatever levels the filters leave visible; when that crosses accounting
  // universes (State LOLF + local M57…), the column is not a consolidated sum (FSC-42).
  const mixed = mixesPerimeters(nodes.map((n) => n.level));

  return (
    <div className="stack" style={{ padding: "var(--sp-5)" }}>
      <p className="fr-sm text-mention">
        Équivalent tabulaire, synchronisé avec les filtres. Tri par colonne ; chaque institution
        renvoie à sa fiche.
      </p>
      {mixed ? <MethodologyNote mixed /> : null}
      <DataTable
        caption={`Institutions affichées (${nodes.length})`}
        columns={nodeCols}
        rows={nodes}
        getRowKey={(r) => r.siren}
      />
      <DataTable
        caption={`Relations affichées (${rels.length})`}
        columns={relCols}
        rows={rels}
        getRowKey={(r) => `${r.source_siren}|${r.target_siren}|${r.type}`}
      />
    </div>
  );
}

export default function GraphPage() {
  const data = useGraphData();
  const navigate = useNavigate();
  const apiRef = useRef<GraphApi | null>(null);

  const [filters, setFilters] = useState<GraphFilters>(defaultFilters);
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set());
  const [focus, setFocus] = useState<string | null>(null);
  const [view, setView] = useState<"graph" | "table">("graph");
  const [counts, setCounts] = useState({ shown: 0, total: 0 });
  const [locate, setLocate] = useState<string | null>(null);
  const [resetSig, setResetSig] = useState(0);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [query, setQuery] = useState("");
  const reduceMotion = useMemo(() => prefersReducedMotion(), []);

  const model = data.status === "ready" ? data.model : null;

  const onFocus = useCallback((s: string | null) => setFocus(s), []);
  const onExpand = useCallback((s: string) => setExpanded((prev) => new Set(prev).add(s)), []);
  const onOpenSheet = useCallback((s: string) => navigate(`/entity/${s}`), [navigate]);
  const onLocate = useCallback((s: string) => {
    setLocate(s);
    setFocus(s);
    setExpanded((prev) => new Set(prev).add(s));
  }, []);

  function resetView() {
    setFilters(defaultFilters());
    setExpanded(new Set());
    setFocus(null);
    setQuery("");
    setResetSig((x) => x + 1);
  }
  function expandAll() {
    if (model) setExpanded(new Set(model.nodes.map((n) => n.siren)));
    setResetSig((x) => x + 1);
  }
  function collapseAll() {
    setExpanded(new Set());
    setFocus(null);
    setResetSig((x) => x + 1);
  }

  const ministries = useMemo(() => (model ? model.nodes.filter((n) => n.isMinistry) : []), [model]);
  const matches = useMemo(() => {
    if (!model || query.length < 2) return [];
    const needle = query.toLowerCase();
    return model.nodes
      .filter((n) => n.resolved && `${n.name} ${n.acronym ?? ""}`.toLowerCase().includes(needle))
      .slice(0, 6);
  }, [model, query]);

  return (
    <div className="page fr-container">
      <div className="page-head">
        <Breadcrumb items={[{ label: "Accueil", to: "/" }, { label: "Graphe institutionnel" }]} />
        <div className="section-head" style={{ marginTop: 12, marginBottom: 0 }}>
          <div className="section-head__title">
            <span className="eyebrow">Exploration</span>
            <h1 className="fr-h1">Graphe institutionnel</h1>
          </div>
          <div className="row-center wrap">
            <ExampleFlag>Données d’exemple</ExampleFlag>
            <div className="viewtoggle" role="group" aria-label="Mode d’affichage">
              <button aria-pressed={view === "graph"} onClick={() => setView("graph")}>
                <GraphIcon /> Vue graphe
              </button>
              <button aria-pressed={view === "table"} onClick={() => setView("table")}>
                <TableIcon /> Vue tableau
              </button>
            </div>
          </div>
        </div>
        <p className="fr-lead" style={{ marginTop: 12, maxWidth: "70ch" }}>
          Choisissez une institution pour voir qui l’encadre, à quoi elle sert et où va son argent.
          Cliquez un nœud pour déplier ses voisins, double-cliquez pour ouvrir sa fiche.
        </p>
      </div>

      <div className="graph-shell">
        <div className="graph-toolbar">
          <div
            className="searchbar"
            style={{ position: "relative", maxWidth: 280, flex: "1 1 220px" }}
          >
            <input
              className="input"
              placeholder="Localiser une institution…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              aria-label="Localiser une institution dans le graphe"
            />
            <Button aria-label="Localiser">
              <SearchIcon />
            </Button>
            {matches.length ? (
              <ul
                style={{
                  position: "absolute",
                  top: "100%",
                  left: 0,
                  right: 0,
                  background: "#fff",
                  border: "1px solid var(--border-default)",
                  borderRadius: "0 0 6px 6px",
                  zIndex: 12,
                  boxShadow: "var(--shadow-md)",
                  maxHeight: 240,
                  overflowY: "auto",
                }}
              >
                {matches.map((m) => (
                  <li key={m.siren}>
                    <button
                      type="button"
                      className="header__tool-link"
                      style={{ width: "100%", justifyContent: "flex-start", padding: "8px 12px" }}
                      onClick={() => {
                        onLocate(m.siren);
                        setQuery("");
                      }}
                    >
                      <LevelShape level={m.level} size={11} /> {m.name}
                    </button>
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
          <Button
            variant="tertiary"
            size="sm"
            className="burger"
            aria-expanded={filtersOpen}
            onClick={() => setFiltersOpen((o) => !o)}
          >
            <Filter /> Filtres
          </Button>
          <div className="row-center wrap" style={{ gap: 6, marginLeft: "auto" }}>
            <span className="graph-count" aria-live="polite">
              <strong>{counts.shown}</strong> institutions affichées sur {counts.total}
            </span>
            <Button variant="tertiary" size="sm" onClick={expandAll}>
              <Layers /> Tout déplier
            </Button>
            <Button variant="tertiary" size="sm" onClick={collapseAll}>
              Replier
            </Button>
            <Button variant="tertiary" size="sm" onClick={resetView}>
              <Reset /> Réinitialiser
            </Button>
          </div>
        </div>

        {view === "table" && model ? (
          <div style={{ gridColumn: "1 / -1" }}>
            <GraphTableView model={model} filters={filters} />
          </div>
        ) : (
          <>
            <FiltersPanel
              filters={filters}
              setFilters={setFilters}
              ministries={ministries}
              open={filtersOpen}
            />
            <div className="graph-canvas-wrap" style={{ position: "relative", padding: 0 }}>
              {data.status === "loading" ? (
                <StateBlock title="Chargement du graphe…">Préparation du réseau…</StateBlock>
              ) : data.status === "error" ? (
                <StateBlock
                  variant="error"
                  icon={<Warning />}
                  title="Le graphe n’a pas pu être chargé"
                >
                  La connexion aux données a échoué. Réessayez ; sinon, consultez l’équivalent
                  tabulaire.
                </StateBlock>
              ) : counts.total > 0 && counts.shown === 0 && model ? (
                <>
                  <GraphCanvas
                    model={model}
                    filters={filters}
                    expanded={expanded}
                    focus={focus}
                    onFocus={onFocus}
                    onExpand={onExpand}
                    onOpenSheet={onOpenSheet}
                    onCounts={setCounts}
                    locate={locate}
                    resetSignal={resetSig}
                    reduceMotion={reduceMotion}
                    apiRef={apiRef}
                  />
                  <div style={{ position: "absolute", inset: 0, background: "#fbfbfd" }}>
                    <StateBlock icon={<SearchIcon />} title="Aucune institution ne correspond">
                      Vos filtres masquent toutes les institutions. Élargissez les niveaux, baissez
                      le montant minimum ou réinitialisez la vue.
                    </StateBlock>
                  </div>
                </>
              ) : (
                <>
                  <GraphCanvas
                    model={model!}
                    filters={filters}
                    expanded={expanded}
                    focus={focus}
                    onFocus={onFocus}
                    onExpand={onExpand}
                    onOpenSheet={onOpenSheet}
                    onCounts={setCounts}
                    locate={locate}
                    resetSignal={resetSig}
                    reduceMotion={reduceMotion}
                    apiRef={apiRef}
                  />
                  <div className="zoom-controls">
                    <button aria-label="Zoom avant" onClick={() => apiRef.current?.zoomIn()}>
                      <Plus />
                    </button>
                    <button aria-label="Zoom arrière" onClick={() => apiRef.current?.zoomOut()}>
                      <Minus />
                    </button>
                    <button aria-label="Ajuster la vue" onClick={() => apiRef.current?.fit()}>
                      <Reset />
                    </button>
                  </div>
                  <GraphLegend />
                  <EntityPanel
                    siren={focus}
                    model={model!}
                    expanded={expanded}
                    onClose={() => setFocus(null)}
                    onOpenSheet={onOpenSheet}
                    onExpand={onExpand}
                    onLocate={onLocate}
                  />
                </>
              )}
            </div>
          </>
        )}
      </div>

      <Callout tone="info" style={{ marginTop: 24 }}>
        <div className="row-center" style={{ gap: 10, alignItems: "flex-start" }}>
          <Keyboard
            style={{ width: 22, height: 22, color: "var(--info)", flex: "none", marginTop: 2 }}
          />
          <div>
            <strong className="fr-sm" style={{ color: "var(--grey-title)" }}>
              Accessibilité — navigation clavier et équivalent tabulaire
            </strong>
            <p className="fr-sm" style={{ marginTop: 4 }}>
              Le graphe est navigable au clavier (Tab pour entrer, flèches pour passer d’une
              institution à l’autre, Entrée pour ouvrir la fiche, Échap pour désélectionner). La{" "}
              <button type="button" className="fr-link" onClick={() => setView("table")}>
                Vue tableau
              </button>{" "}
              fournit le même contenu, triable et synchronisé. Les niveaux sont distingués par forme{" "}
              <em>et</em> couleur (palette compatible daltonisme).
            </p>
          </div>
        </div>
      </Callout>
    </div>
  );
}
