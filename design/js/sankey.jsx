/* Sankey flow diagram (hand-rolled SVG layout). → window.Sankey, window.FluxPage */

function computeSankey(links, width, height, pad) {
  // derive nodes + columns
  const nodeMap = new Map();
  function getNode(id, col, label, level) {
    if (!nodeMap.has(id)) nodeMap.set(id, { id, col, label, level, value: 0, sourceLinks: [], targetLinks: [] });
    const n = nodeMap.get(id);
    if (col != null) n.col = col;
    return n;
  }
  links.forEach((l) => {
    const s = getNode(l.source, l.sourceCol, l.sourceLabel, l.sourceLevel);
    const t = getNode(l.target, l.targetCol, l.targetLabel, l.targetLevel);
    s.sourceLinks.push(l); t.targetLinks.push(l);
  });
  const nodes = [...nodeMap.values()];
  nodes.forEach((n) => {
    const out = n.sourceLinks.reduce((s, l) => s + l.value, 0);
    const inc = n.targetLinks.reduce((s, l) => s + l.value, 0);
    n.value = Math.max(out, inc);
  });
  const cols = [...new Set(nodes.map((n) => n.col))].sort((a, b) => a - b);
  const colX = {};
  const nodeW = 16;
  cols.forEach((c, i) => { colX[c] = pad + (i * (width - pad * 2 - nodeW)) / (cols.length - 1 || 1); });
  const maxVal = Math.max(...nodes.map((n) => n.value), 1);
  const totalByCol = {};
  cols.forEach((c) => { totalByCol[c] = nodes.filter((n) => n.col === c).reduce((s, n) => s + n.value, 0); });
  const gap = 14;
  cols.forEach((c) => {
    const colNodes = nodes.filter((n) => n.col === c).sort((a, b) => b.value - a.value);
    const totalGap = gap * (colNodes.length - 1);
    const scale = (height - pad * 2 - totalGap) / (totalByCol[c] || 1);
    let y = pad;
    colNodes.forEach((n) => {
      n.x = colX[c]; n.w = nodeW; n.h = Math.max(3, n.value * scale); n.y = y; n.sy = y; n.ty = y;
      y += n.h + gap;
    });
  });
  // assign link y positions
  nodes.forEach((n) => {
    n.sourceLinks.sort((a, b) => (nodeMap.get(a.target).y) - (nodeMap.get(b.target).y));
    let sy = n.y;
    n.sourceLinks.forEach((l) => { const scale = n.h / (n.value || 1); l.sw = l.value * scale; l.sy0 = sy + l.sw / 2; sy += l.sw; });
    n.targetLinks.sort((a, b) => (nodeMap.get(a.source).y) - (nodeMap.get(b.source).y));
    let ty = n.y;
    n.targetLinks.forEach((l) => { const scale = n.h / (n.value || 1); l.tw = l.value * scale; l.ty0 = ty + l.tw / 2; ty += l.tw; });
  });
  return { nodes, links, nodeMap, nodeW };
}

function Sankey({ links, height = 460 }) {
  const wrapRef = React.useRef(null);
  const [w, setW] = React.useState(900);
  const [hover, setHover] = React.useState(null);
  React.useEffect(() => {
    const ro = new ResizeObserver((ents) => { setW(ents[0].contentRect.width); });
    if (wrapRef.current) ro.observe(wrapRef.current);
    return () => ro.disconnect();
  }, []);
  const layout = React.useMemo(() => computeSankey(links.map((l) => ({ ...l })), w, height, 28), [links, w, height]);
  const { nodes, nodeMap } = layout;

  function ribbon(l) {
    const s = nodeMap.get(l.source), t = nodeMap.get(l.target);
    const x0 = s.x + s.w, x1 = t.x;
    const xm = (x0 + x1) / 2;
    return `M${x0},${l.sy0} C${xm},${l.sy0} ${xm},${l.ty0} ${x1},${l.ty0}`;
  }
  const colTitles = ["Financeur public", "Opérateur", "Titulaire / délégataire"];

  return (
    <div ref={wrapRef} style={{ width: "100%" }}>
      <svg width={w} height={height} role="img" aria-label="Diagramme de flux de financement (Sankey). Un équivalent tabulaire est fourni ci-dessous.">
        {/* column headers */}
        {[...new Set(nodes.map((n) => n.col))].sort((a, b) => a - b).map((c, i, arr) => {
          const colNodes = nodes.filter((n) => n.col === c);
          const x = colNodes[0] ? colNodes[0].x + colNodes[0].w / 2 : 0;
          return <text key={c} x={x} y={14} className="sankey-node-sub" textAnchor="middle" style={{ fontWeight: 700, fill: "#666" }}>{colTitles[i]}</text>;
        })}
        {/* links */}
        {layout.links.map((l, i) => {
          const active = hover == null || hover === l.source || hover === l.target;
          const color = l.type === "delegates" ? "#e69f00" : (l.type === "participation" ? "#009e73" : "#0072b2");
          return (
            <path key={i} className="sankey-link" d={ribbon(l)} stroke={color}
              strokeWidth={Math.max(1, l.sw)} strokeOpacity={active ? 0.34 : 0.07}
              onMouseEnter={() => setHover(l.source)} onMouseLeave={() => setHover(null)}>
              <title>{l.sourceLabel} → {l.targetLabel} : {window.U.euroFull(l.value)} ({l.exercice || "exemple"})</title>
            </path>
          );
        })}
        {/* nodes */}
        {nodes.map((n) => {
          const m = window.U.levelMeta(n.level);
          const right = n.col === Math.max(...nodes.map((x) => x.col));
          return (
            <g key={n.id} onMouseEnter={() => setHover(n.id)} onMouseLeave={() => setHover(null)} style={{ cursor: "default" }}>
              <rect x={n.x} y={n.y} width={n.w} height={n.h} rx="2" fill={n.level ? m.color : "#888"} opacity={hover == null || hover === n.id ? 1 : 0.5}></rect>
              <text x={right ? n.x - 6 : n.x + n.w + 6} y={n.y + n.h / 2 - 4} className="sankey-node-label" textAnchor={right ? "end" : "start"} dominantBaseline="middle">
                {n.label.length > 30 ? n.label.slice(0, 28) + "…" : n.label}
              </text>
              <text x={right ? n.x - 6 : n.x + n.w + 6} y={n.y + n.h / 2 + 9} className="sankey-node-sub" textAnchor={right ? "end" : "start"} dominantBaseline="middle">
                {window.U.euroCompact(n.value)}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

// Build the flow links for a given root ministry
function buildFlowLinks(rootSiren) {
  const links = [];
  const root = window.U.entity(rootSiren);
  // ministry -> operators (funds)
  window.DATA.edges.filter((e) => e.source_siren === rootSiren && e.type === "funds" && e.amount_eur).forEach((e) => {
    const op = window.U.entity(e.target_siren);
    links.push({ source: rootSiren, target: e.target_siren, value: e.amount_eur, type: "funds", exercice: e.exercice,
      sourceCol: 0, sourceLabel: root.acronym || root.name, sourceLevel: root.level,
      targetCol: 1, targetLabel: op.acronym || op.name, targetLevel: op.level });
    // operator -> titulaires (delegates)
    window.DATA.edges.filter((d) => d.source_siren === e.target_siren && d.type === "delegates" && d.amount_eur).forEach((d) => {
      const ti = window.U.entity(d.target_siren);
      links.push({ source: e.target_siren, target: d.target_siren, value: d.amount_eur, type: "delegates", exercice: d.exercice,
        sourceCol: 1, sourceLabel: op.acronym || op.name, sourceLevel: op.level,
        targetCol: 2, targetLabel: ti.name, targetLevel: ti.level });
    });
  });
  return links;
}

function FluxPage({ go, params }) {
  const ministries = window.DATA.entities.filter((e) => e.category === "ministère");
  const [root, setRoot] = React.useState((params && params.focus) || ministries[1].siren);
  const links = React.useMemo(() => buildFlowLinks(root), [root]);
  const rootE = window.U.entity(root);
  const totalOut = links.filter((l) => l.sourceCol === 0).reduce((s, l) => s + l.value, 0);

  const tableRows = links.map((l, i) => ({ i, from: l.sourceLabel, to: l.targetLabel, type: l.type, value: l.value, exercice: l.exercice }));
  const tableCols = [
    { key: "from", header: "De" },
    { key: "to", header: "Vers" },
    { key: "type", header: "Type", render: (r) => <span className="tag tag--sm">{({ funds: "Financement", delegates: "Délégation", participation: "Participation" })[r.type]}</span> },
    { key: "value", header: "Montant", num: true, render: (r) => <span className="tnum">{window.U.euroCompact(r.value)}</span>, sortValue: (r) => r.value },
    { key: "exercice", header: "Millésime", num: true, render: (r) => r.exercice || "—" },
  ];

  return (
    <div className="page fr-container">
      <div className="page-head">
        <nav className="breadcrumb" aria-label="Fil d’Ariane"><a href="#/accueil">Accueil</a><span className="breadcrumb__sep">›</span><span>Flux de financement</span></nav>
        <div className="section-head" style={{ marginTop: 12, marginBottom: 0 }}>
          <div className="section-head__title">
            <span className="eyebrow">Suivre l’argent</span>
            <h1 className="fr-h1">Flux de financement</h1>
          </div>
          <window.ExampleFlag>Montants d’exemple</window.ExampleFlag>
        </div>
        <p className="fr-lead" style={{ marginTop: 12, maxWidth: "70ch" }}>Du financeur public à l’opérateur, puis au titulaire du marché ou au délégataire. Survolez un flux pour son montant et sa provenance.</p>
      </div>

      <div className="row-center wrap" style={{ marginBottom: 16, gap: 10 }}>
        <label className="field__label" htmlFor="flux-root">Focaliser sur :</label>
        <select id="flux-root" className="select" style={{ maxWidth: 420 }} value={root} onChange={(e) => setRoot(e.target.value)}>
          {ministries.map((m) => <option key={m.siren} value={m.siren}>{m.name}</option>)}
        </select>
        <span className="fr-sm text-mention">Total tracé : <strong className="tnum" style={{ color: "var(--grey-title)" }}>{window.U.euroCompact(totalOut)}</strong></span>
      </div>

      <div className="sankey-wrap">
        {links.length ? <Sankey links={links} /> : <div className="state-block"><window.Icon.Flow className="state-block__icon" /><h3 className="fr-h4">Aucun flux disponible</h3><p>Cette entité ne publie pas de flux de financement vers des opérateurs dans le périmètre suivi.</p></div>}
      </div>

      <div className="row-center wrap" style={{ gap: 16, marginTop: 12 }}>
        <span className="legend__row"><svg width="22" height="8"><rect width="22" height="8" rx="2" fill="#0072b2" opacity="0.4"/></svg> Financement (subvention)</span>
        <span className="legend__row"><svg width="22" height="8"><rect width="22" height="8" rx="2" fill="#e69f00" opacity="0.5"/></svg> Délégation / marché</span>
        <span className="fr-sm text-mention" style={{ marginLeft: "auto" }}>Attention : un même euro peut être compté plusieurs fois (double-comptage entre niveaux). Voir <a className="fr-link" href="#/donnees">méthodologie</a>.</span>
      </div>

      <h2 className="fr-h3" style={{ marginTop: 40, marginBottom: 16 }}>Équivalent tabulaire</h2>
      <window.DataTable caption={`Flux de financement — ${rootE.name} (exemple)`} columns={tableCols} rows={tableRows} getRowKey={(r) => r.i} />
    </div>
  );
}

window.Sankey = Sankey;
window.FluxPage = FluxPage;
window.buildFlowLinks = buildFlowLinks;
