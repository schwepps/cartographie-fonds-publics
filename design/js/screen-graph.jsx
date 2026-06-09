/* Screen 2 — Graphe institutionnel. → window.GraphPage */

const DEFAULT_FILTERS = () => ({
  levels: { etat: true, local: true, social: true, delegue: true },
  ministry: "all",
  minAmount: 0,
  linkTypes: { tutelle: true, funds: true, participation: true, delegates: true },
});

const MIN_AMOUNT_STEPS = [0, 10e6, 100e6, 1e9, 10e9];

function GraphLegend() {
  const L = window.DATA.LEVELS;
  return (
    <div className="legend" aria-hidden="false">
      <h4>Niveau (forme + couleur)</h4>
      {Object.values(L).map((m) => (
        <div className="legend__row" key={m.id}>
          <span className="legend__swatch"><window.LevelShape level={m.id} size={13} /></span>
          {m.label} <span className="fr-xs text-mention">· {m.desc}</span>
        </div>
      ))}
      <h4 style={{ marginTop: 10 }}>Liens</h4>
      <div className="legend__row"><svg width="24" height="10" aria-hidden="true"><line x1="1" y1="5" x2="23" y2="5" stroke="#7a7a86" strokeWidth="2" /></svg> Tutelle</div>
      <div className="legend__row"><svg width="24" height="10" aria-hidden="true"><line x1="1" y1="5" x2="23" y2="5" stroke="#0072b2" strokeWidth="3.4" /></svg> Financement <span className="fr-xs text-mention">(épaisseur ∝ montant)</span></div>
      <div className="legend__row"><svg width="24" height="10" aria-hidden="true"><line x1="1" y1="5" x2="23" y2="5" stroke="#cf7a00" strokeWidth="2" strokeDasharray="5 4" /></svg> Délégation</div>
      <div className="legend__row fr-xs text-mention" style={{ marginTop: 4 }}>Taille du nœud ∝ crédits de paiement (échelle log)</div>
    </div>
  );
}

function FiltersPanel({ filters, setFilters, open }) {
  const L = window.DATA.LEVELS;
  const ministries = window.DATA.entities.filter((e) => e.category === "ministère");
  const set = (patch) => setFilters((f) => ({ ...f, ...patch }));
  return (
    <div className={`graph-filters ${open ? "open" : ""}`}>
      <div className="stack">
        <div>
          <h4 className="fr-h4" style={{ fontSize: "0.9rem", marginBottom: 8 }}>Niveau</h4>
          {Object.values(L).map((m) => (
            <label className="check-row" key={m.id}>
              <input type="checkbox" checked={filters.levels[m.id]} onChange={(e) => set({ levels: { ...filters.levels, [m.id]: e.target.checked } })} />
              <window.LevelShape level={m.id} size={11} /> {m.label}
            </label>
          ))}
        </div>
        <div className="field">
          <label className="field__label" htmlFor="f-min">Tutelle (ministère)</label>
          <select id="f-min" className="select" value={filters.ministry} onChange={(e) => set({ ministry: e.target.value })}>
            <option value="all">Toutes les tutelles</option>
            {ministries.map((m) => <option key={m.siren} value={m.siren}>{m.acronym || m.name}</option>)}
          </select>
        </div>
        <div className="field">
          <label className="field__label" htmlFor="f-amt">Montant minimum (CP) : <strong>{filters.minAmount === 0 ? "tous" : window.U.euroCompact(filters.minAmount)}</strong></label>
          <input id="f-amt" type="range" min="0" max={MIN_AMOUNT_STEPS.length - 1} step="1"
            value={MIN_AMOUNT_STEPS.indexOf(filters.minAmount)}
            onChange={(e) => set({ minAmount: MIN_AMOUNT_STEPS[+e.target.value] })}
            style={{ accentColor: "var(--blue-france)" }} />
          <span className="field__hint">Les ministères restent toujours affichés.</span>
        </div>
        <div>
          <h4 className="fr-h4" style={{ fontSize: "0.9rem", marginBottom: 8 }}>Type de lien</h4>
          {[["tutelle", "Tutelle"], ["funds", "Financement"], ["participation", "Participation"], ["delegates", "Délégation"]].map(([k, lab]) => (
            <label className="check-row" key={k}>
              <input type="checkbox" checked={filters.linkTypes[k]} onChange={(e) => set({ linkTypes: { ...filters.linkTypes, [k]: e.target.checked } })} />
              {lab}
            </label>
          ))}
        </div>
      </div>
    </div>
  );
}

function EntityPanel({ siren, onClose, onOpenSheet, onExpand, expanded, onLocate }) {
  if (!siren) return null;
  const e = window.U.entity(siren);
  if (!e) return null;
  const chain = window.U.tutelleChain(siren);
  const children = window.U.childrenOf(siren);
  const out = window.U.outflows(siren).sort((a, b) => b.amount_eur - a.amount_eur).slice(0, 4);
  const budget = window.U.budgetOf(siren);
  const totalCp = budget.filter((b) => !b.executed).reduce((s, b) => s + (b.amount_cp_eur || 0), 0);
  const canExpand = window.U.edgesOf(siren).some((ed) => {
    const o = ed.source_siren === siren ? ed.target_siren : ed.source_siren;
    return true;
  }) && !expanded.has(siren);

  return (
    <aside className="entity-panel open" aria-label={`Résumé : ${e.name}`}>
      <button className="btn btn--tertiary btn--icon-only panel-close" aria-label="Fermer le panneau" onClick={onClose}><window.Icon.Close /></button>
      <div className="entity-panel__head">
        <div style={{ marginBottom: 10 }}><window.LevelBadge level={e.level} unresolved={e.resolved === false} /></div>
        <h2 className="fr-h3" style={{ marginBottom: 6 }}>{e.name}</h2>
        <div className="breadcrumb">
          {chain.map((c, i) => (
            <React.Fragment key={c.siren}>
              {i > 0 ? <span className="breadcrumb__sep">›</span> : null}
              {c.siren === siren ? <span>{c.acronym || c.name}</span> : <a href="#" onClick={(ev) => { ev.preventDefault(); onLocate(c.siren); }}>{c.acronym || c.name}</a>}
            </React.Fragment>
          ))}
        </div>
      </div>
      <div className="entity-panel__body stack">
        <div>
          <div className="fr-xs text-mention" style={{ textTransform: "uppercase", letterSpacing: ".04em", marginBottom: 4 }}>Crédits de paiement (CP) — exemple</div>
          <div className="figure__value" style={{ fontSize: "1.6rem" }}>{window.U.euroCompact(e.cp_eur)}</div>
          {totalCp > 0 ? <div className="fr-xs text-mention">Dont {window.U.euroCompact(totalCp)} votés en LFI 2025 (programmes suivis)</div> : null}
        </div>
        <dl className="kv">
          <dt>SIREN</dt><dd>{e.resolved === false ? <span className="text-mention">non résolu</span> : <span className="mono">{e.siren}</span>}</dd>
          <dt>Catégorie</dt><dd>{e.category || "—"}</dd>
          <dt>Tutelle</dt><dd>{e.parent_siren ? window.U.nameOf(e.parent_siren) : "—"}</dd>
        </dl>
        {children.length ? (
          <div>
            <div className="fr-sm" style={{ fontWeight: 600, marginBottom: 6 }}>Opérateurs sous tutelle ({children.length})</div>
            <div className="row wrap" style={{ gap: 6 }}>
              {children.slice(0, 6).map((c) => <window.Chip key={c.siren} sm level={c.level} onClick={() => onLocate(c.siren)}>{c.acronym || c.name.split(" ").slice(0, 3).join(" ")}</window.Chip>)}
              {children.length > 6 ? <span className="tag tag--sm">+{children.length - 6}</span> : null}
            </div>
          </div>
        ) : null}
        {out.length ? (
          <div>
            <div className="fr-sm" style={{ fontWeight: 600, marginBottom: 6 }}>Où va son argent (top {out.length})</div>
            <div className="bars">
              {out.map((o, i) => {
                const max = out[0].amount_eur;
                return (
                  <div className="bar-row" key={i}>
                    <div className="bar-row__head"><span>{window.U.nameOf(o.target_siren).split(" ").slice(0, 4).join(" ")}</span><span className="tnum">{window.U.euroCompact(o.amount_eur)}</span></div>
                    <div className="bar-row__track"><div className="bar-row__fill" style={{ width: (o.amount_eur / max * 100) + "%", background: o.type === "delegates" ? "var(--niv-delegue)" : "var(--seq-5)" }}></div></div>
                  </div>
                );
              })}
            </div>
          </div>
        ) : null}
        <div className="fr-xs"><window.ProvenanceBadge provId={e.provenance} millesime={window.U.sourceOf(e.provenance) && window.U.sourceOf(e.provenance).millesime} /></div>
      </div>
      <div className="entity-panel__foot">
        {canExpand ? <button className="btn btn--secondary btn--sm" onClick={() => onExpand(siren)}><window.Icon.Plus /> Déplier</button> : null}
        <button className="btn btn--primary btn--sm" onClick={() => onOpenSheet(siren)} style={{ marginLeft: "auto" }}>Ouvrir la fiche <window.Icon.Arrow /></button>
      </div>
    </aside>
  );
}

function GraphTableView({ filters }) {
  // synchronized table: same filtered nodes + edges
  const nodes = window.DATA.entities.filter((n) => filters.levels[n.level] && (filters.ministry === "all" || n.level !== "etat" || window.U.tutelleChain(n.siren)[0].siren === filters.ministry) && (filters.minAmount === 0 || (n.cp_eur || 0) >= filters.minAmount || n.category === "ministère"));
  const visSet = new Set(nodes.map((n) => n.siren));
  const rels = window.DATA.edges.filter((e) => filters.linkTypes[e.type] !== false && visSet.has(e.source_siren) && visSet.has(e.target_siren));

  const nodeCols = [
    { key: "name", header: "Institution", render: (r) => <a className="fr-link" href={`#/fiche/${r.siren}`}>{r.name}</a>, sortValue: (r) => r.name },
    { key: "level", header: "Niveau", render: (r) => <window.LevelBadge level={r.level} unresolved={r.resolved === false} />, sortValue: (r) => r.level },
    { key: "category", header: "Catégorie", render: (r) => r.category || "—" },
    { key: "cp", header: "CP (exemple)", num: true, render: (r) => <span className="tnum">{window.U.euroCompact(r.cp_eur)}</span>, sortValue: (r) => r.cp_eur || 0 },
  ];
  const relCols = [
    { key: "source", header: "Source", render: (r) => <a className="fr-link" href={`#/fiche/${r.source_siren}`}>{window.U.nameOf(r.source_siren)}</a>, sortValue: (r) => window.U.nameOf(r.source_siren) },
    { key: "type", header: "Relation", render: (r) => <span className="tag tag--sm">{({ tutelle: "Tutelle", funds: "Financement", participation: "Participation", delegates: "Délégation" })[r.type]}</span> },
    { key: "target", header: "Cible", render: (r) => <a className="fr-link" href={`#/fiche/${r.target_siren}`}>{window.U.nameOf(r.target_siren)}</a>, sortValue: (r) => window.U.nameOf(r.target_siren) },
    { key: "amount", header: "Montant", num: true, render: (r) => <span className="tnum">{window.U.euroCompact(r.amount_eur)}</span>, sortValue: (r) => r.amount_eur || 0 },
    { key: "exercice", header: "Millésime", num: true, render: (r) => r.exercice || "—" },
  ];
  return (
    <div className="stack" style={{ padding: "var(--sp-5)" }}>
      <p className="fr-sm text-mention">Équivalent tabulaire, synchronisé avec les filtres. Tri par colonne ; chaque institution renvoie à sa fiche.</p>
      <window.DataTable caption={`Institutions affichées (${nodes.length})`} columns={nodeCols} rows={nodes} getRowKey={(r) => r.siren} />
      <window.DataTable caption={`Relations affichées (${rels.length})`} columns={relCols} rows={rels} getRowKey={(r) => r.source_siren + r.target_siren + r.type} />
    </div>
  );
}

function StateBlock({ kind, onRetry }) {
  if (kind === "loading") {
    return (
      <div className="state-block" role="status" aria-live="polite">
        <div style={{ width: "70%", maxWidth: 520, display: "flex", flexDirection: "column", gap: 14 }}>
          <div className="skeleton" style={{ height: 28, width: "55%" }}></div>
          <div style={{ position: "relative", height: 280 }}>
            {[[20, 30, 60], [70, 20, 40], [45, 60, 80], [80, 70, 50], [30, 75, 44]].map((c, i) => (
              <div key={i} className="skeleton" style={{ position: "absolute", left: c[0] + "%", top: c[1] + "%", width: c[2], height: c[2], borderRadius: "50%" }}></div>
            ))}
          </div>
          <div className="fr-sm text-mention" style={{ textAlign: "center" }}>Chargement du graphe…</div>
        </div>
      </div>
    );
  }
  if (kind === "empty") {
    return (
      <div className="state-block">
        <window.Icon.Search className="state-block__icon" />
        <h3 className="fr-h4">Aucune institution ne correspond</h3>
        <p>Vos filtres masquent toutes les institutions. Élargissez les niveaux, baissez le montant minimum ou réinitialisez la vue.</p>
        <button className="btn btn--secondary btn--sm" onClick={onRetry}><window.Icon.Reset /> Réinitialiser les filtres</button>
      </div>
    );
  }
  if (kind === "error") {
    return (
      <div className="state-block state-block--error" role="alert">
        <window.Icon.Warning className="state-block__icon" />
        <h3 className="fr-h4">Le graphe n’a pas pu être chargé</h3>
        <p>La connexion aux données (Supabase) a échoué. Réessayez ; si le problème persiste, consultez l’équivalent tabulaire.</p>
        <button className="btn btn--primary btn--sm" onClick={onRetry}><window.Icon.Reset /> Réessayer</button>
      </div>
    );
  }
  return null;
}

function GraphPage({ params, go }) {
  const [filters, setFilters] = React.useState(DEFAULT_FILTERS);
  const [expanded, setExpanded] = React.useState(() => new Set());
  const [focus, setFocus] = React.useState(null);
  const [view, setView] = React.useState("graph");
  const [counts, setCounts] = React.useState({ shown: 0, total: 0 });
  const [locate, setLocate] = React.useState(null);
  const [resetSig, setResetSig] = React.useState(0);
  const [filtersOpen, setFiltersOpen] = React.useState(false);
  const [demo, setDemo] = React.useState("ready"); // ready|loading|empty|error
  const [query, setQuery] = React.useState("");
  const reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // deep-link: locate a siren passed in params
  React.useEffect(() => {
    if (params && params.locate) { setLocate(params.locate); setFocus(params.locate); setExpanded((s) => new Set(s).add(params.locate)); }
  }, [params]);

  const toggleExpand = React.useCallback((siren) => setExpanded((s) => { const n = new Set(s); n.add(siren); return n; }), []);
  const onFocus = React.useCallback((s) => setFocus(s), []);
  const openSheet = React.useCallback((s) => go(`fiche/${s}`), [go]);
  const onLocate = React.useCallback((s) => { setLocate(s); setFocus(s); setExpanded((x) => new Set(x).add(s)); }, []);

  function resetView() {
    setFilters(DEFAULT_FILTERS());
    setExpanded(new Set());
    setFocus(null); setQuery(""); setResetSig((x) => x + 1);
  }
  function expandAll() { setExpanded(new Set(window.DATA.entities.map((e) => e.siren))); setResetSig((x) => x + 1); }
  function collapseAll() { setExpanded(new Set()); setFocus(null); setResetSig((x) => x + 1); }

  // search-to-locate
  const matches = query.length >= 2 ? window.DATA.entities.filter((e) => (e.name + " " + (e.acronym || "")).toLowerCase().includes(query.toLowerCase())).slice(0, 6) : [];

  const isEmptyState = demo === "ready" && counts.shown === 0;

  return (
    <div className="page fr-container">
      <div className="page-head">
        <nav className="breadcrumb" aria-label="Fil d’Ariane"><a href="#/accueil">Accueil</a><span className="breadcrumb__sep">›</span><span>Graphe institutionnel</span></nav>
        <div className="section-head" style={{ marginTop: 12, marginBottom: 0 }}>
          <div className="section-head__title">
            <span className="eyebrow">Exploration</span>
            <h1 className="fr-h1">Graphe institutionnel</h1>
          </div>
          <div className="row-center wrap">
            <window.ExampleFlag>Données d’exemple</window.ExampleFlag>
            <div className="viewtoggle" role="group" aria-label="Mode d’affichage">
              <button aria-pressed={view === "graph"} onClick={() => setView("graph")}><window.Icon.Graph /> Vue graphe</button>
              <button aria-pressed={view === "table"} onClick={() => setView("table")}><window.Icon.Table /> Vue tableau</button>
            </div>
          </div>
        </div>
        <p className="fr-lead" style={{ marginTop: 12, maxWidth: "70ch" }}>
          Choisissez une institution pour voir qui l’encadre, à quoi elle sert et où va son argent. Cliquez un nœud pour déplier ses voisins, double-cliquez pour ouvrir sa fiche.
        </p>
      </div>

      {/* demo state switch (prototype affordance) */}
      <div className="row-center wrap" style={{ marginBottom: 12, gap: 8 }}>
        <span className="fr-xs text-mention" style={{ textTransform: "uppercase", letterSpacing: ".04em" }}>États (démo) :</span>
        {[["ready", "Normal"], ["loading", "Chargement"], ["empty", "Vide"], ["error", "Erreur"]].map(([k, lab]) => (
          <button key={k} className={`tag tag--sm ${demo === k ? "tag--selected" : ""}`} onClick={() => setDemo(k)}>{lab}</button>
        ))}
      </div>

      <div className="graph-shell">
        <div className="graph-toolbar">
          <div className="searchbar" style={{ position: "relative", maxWidth: 280, flex: "1 1 220px" }}>
            <input className="input" placeholder="Localiser une institution…" value={query} onChange={(e) => setQuery(e.target.value)} aria-label="Localiser une institution dans le graphe" />
            <button className="btn btn--primary" aria-label="Rechercher"><window.Icon.Search /></button>
            {matches.length ? (
              <ul style={{ position: "absolute", top: "100%", left: 0, right: 0, background: "#fff", border: "1px solid var(--border-default)", borderRadius: "0 0 6px 6px", zIndex: 12, boxShadow: "var(--shadow-md)", maxHeight: 240, overflowY: "auto" }}>
                {matches.map((m) => (
                  <li key={m.siren}><button className="header__tool-link" style={{ width: "100%", justifyContent: "flex-start", padding: "8px 12px" }} onClick={() => { onLocate(m.siren); setQuery(""); }}><window.LevelShape level={m.level} size={11} /> {m.name}</button></li>
                ))}
              </ul>
            ) : null}
          </div>
          <button className="btn btn--tertiary btn--sm burger" onClick={() => setFiltersOpen((o) => !o)} aria-expanded={filtersOpen}><window.Icon.Filter /> Filtres</button>
          <div className="row-center wrap" style={{ gap: 6, marginLeft: "auto" }}>
            <span className="graph-count" aria-live="polite"><strong>{counts.shown}</strong> institutions affichées sur {counts.total}</span>
            <button className="btn btn--tertiary btn--sm" onClick={expandAll}><window.Icon.Layers /> Tout déplier</button>
            <button className="btn btn--tertiary btn--sm" onClick={collapseAll}>Replier</button>
            <button className="btn btn--tertiary btn--sm" onClick={resetView}><window.Icon.Reset /> Réinitialiser</button>
          </div>
        </div>

        {view === "table" ? (
          <div style={{ gridColumn: "1 / -1" }}><GraphTableView filters={filters} /></div>
        ) : (
          <React.Fragment>
            <FiltersPanel filters={filters} setFilters={setFilters} open={filtersOpen} />
            <div className="graph-canvas-wrap" style={{ position: "relative", padding: 0 }}>
              {demo === "ready" ? (
                <React.Fragment>
                  <window.GraphCanvas
                    filters={filters} expanded={expanded} focus={focus}
                    onFocus={onFocus} onExpand={toggleExpand} onOpenSheet={openSheet}
                    onCounts={setCounts} locate={locate} resetSignal={resetSig} reduceMotion={reduceMotion}
                  />
                  {isEmptyState ? <div style={{ position: "absolute", inset: 0, background: "#fbfbfd" }}><StateBlock kind="empty" onRetry={resetView} /></div> : null}
                  <div className="zoom-controls">
                    <button aria-label="Zoom avant" onClick={() => window.__graphApi.zoomIn()}><window.Icon.Plus /></button>
                    <button aria-label="Zoom arrière" onClick={() => window.__graphApi.zoomOut()}><window.Icon.Minus /></button>
                    <button aria-label="Ajuster la vue" onClick={() => window.__graphApi.fit()}><window.Icon.Reset /></button>
                  </div>
                  <GraphLegend />
                  <EntityPanel siren={focus} onClose={() => setFocus(null)} onOpenSheet={openSheet} onExpand={toggleExpand} expanded={expanded} onLocate={onLocate} />
                </React.Fragment>
              ) : (
                <StateBlock kind={demo} onRetry={() => setDemo("ready")} />
              )}
            </div>
          </React.Fragment>
        )}
      </div>

      <div className="callout callout--info" style={{ marginTop: 24 }}>
        <div className="row-center" style={{ gap: 10, alignItems: "flex-start" }}>
          <window.Icon.Keyboard style={{ width: 22, height: 22, color: "var(--info)", flex: "none", marginTop: 2 }} />
          <div>
            <strong className="fr-sm" style={{ color: "var(--grey-title)" }}>Accessibilité — navigation clavier et équivalent tabulaire</strong>
            <p className="fr-sm" style={{ marginTop: 4 }}>Le graphe est navigable au clavier (Tab pour entrer, flèches pour passer d’une institution à l’autre, Entrée pour ouvrir la fiche, Échap pour désélectionner). La <button className="fr-link" onClick={() => setView("table")}>Vue tableau</button> fournit le même contenu, triable et synchronisé avec les filtres. Les niveaux sont distingués par forme <em>et</em> couleur (palette compatible daltonisme).</p>
          </div>
        </div>
      </div>
    </div>
  );
}

window.GraphPage = GraphPage;
