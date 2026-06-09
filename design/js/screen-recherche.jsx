/* Screen 5 — Recherche. → window.RecherchePage */

function highlight(text, q) {
  if (!q) return text;
  const idx = text.toLowerCase().indexOf(q.toLowerCase());
  if (idx < 0) return text;
  return <React.Fragment>{text.slice(0, idx)}<mark>{text.slice(idx, idx + q.length)}</mark>{text.slice(idx + q.length)}</React.Fragment>;
}

function RecherchePage({ params, go }) {
  const [q, setQ] = React.useState((params && params.q) || "");
  const [levels, setLevels] = React.useState({ etat: true, local: true, social: true, delegue: true });
  const [tutelle, setTutelle] = React.useState("all");
  const [sort, setSort] = React.useState("amount");
  const ministries = window.DATA.entities.filter((e) => e.category === "ministère");

  const results = React.useMemo(() => {
    let r = window.DATA.entities.filter((e) => {
      if (!levels[e.level]) return false;
      if (tutelle !== "all" && (e.level !== "etat" || window.U.tutelleChain(e.siren)[0].siren !== tutelle)) return false;
      if (q && !(e.name + " " + (e.acronym || "") + " " + (e.category || "")).toLowerCase().includes(q.toLowerCase())) return false;
      return true;
    });
    r = [...r].sort((a, b) => sort === "amount" ? (b.cp_eur || 0) - (a.cp_eur || 0) : a.name.localeCompare(b.name, "fr"));
    return r;
  }, [q, levels, tutelle, sort]);

  // facet counts (by level, ignoring level filter)
  const levelCounts = {};
  Object.keys(window.DATA.LEVELS).forEach((lv) => {
    levelCounts[lv] = window.DATA.entities.filter((e) => e.level === lv && (!q || (e.name + (e.acronym || "")).toLowerCase().includes(q.toLowerCase()))).length;
  });

  return (
    <div className="page fr-container">
      <div className="page-head">
        <nav className="breadcrumb" aria-label="Fil d’Ariane"><a href="#/accueil">Accueil</a><span className="breadcrumb__sep">›</span><span>Recherche</span></nav>
        <h1 className="fr-h1" style={{ marginTop: 12, marginBottom: 16 }}>Rechercher une institution</h1>
        <div className="searchbar" style={{ maxWidth: 620 }}>
          <input className="input" autoFocus placeholder="Nom d’une institution, d’un opérateur, d’un titulaire…" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Terme de recherche" />
          <button className="btn btn--primary"><window.Icon.Search /> Rechercher</button>
        </div>
      </div>

      <div className="search-layout">
        {/* facets */}
        <aside aria-label="Filtres">
          <div className="facet">
            <h4>Niveau</h4>
            {Object.values(window.DATA.LEVELS).map((m) => (
              <label className="check-row" key={m.id}>
                <input type="checkbox" checked={levels[m.id]} onChange={(e) => setLevels({ ...levels, [m.id]: e.target.checked })} />
                <window.LevelShape level={m.id} size={11} /> {m.label}
                <span className="fr-xs text-mention" style={{ marginLeft: "auto" }}>{levelCounts[m.id]}</span>
              </label>
            ))}
          </div>
          <div className="facet">
            <h4>Tutelle</h4>
            <select className="select" value={tutelle} onChange={(e) => setTutelle(e.target.value)}>
              <option value="all">Toutes</option>
              {ministries.map((m) => <option key={m.siren} value={m.siren}>{m.acronym || m.name}</option>)}
            </select>
          </div>
          <div className="facet">
            <h4>Trier par</h4>
            {[["amount", "Montant (CP) décroissant"], ["name", "Nom (A→Z)"]].map(([k, lab]) => (
              <label className="check-row" key={k}><input type="radio" name="sort" checked={sort === k} onChange={() => setSort(k)} /> {lab}</label>
            ))}
          </div>
        </aside>

        {/* results */}
        <div className="stack" style={{ gap: 12 }}>
          <div className="row-center" style={{ justifyContent: "space-between" }}>
            <p className="fr-sm text-mention" aria-live="polite"><strong style={{ color: "var(--grey-title)" }}>{results.length}</strong> résultat{results.length > 1 ? "s" : ""}{q ? <> pour « {q} »</> : null}</p>
            <window.ExampleFlag>Données d’exemple</window.ExampleFlag>
          </div>
          {results.length === 0 ? (
            <div className="state-block" style={{ height: "auto", padding: 48 }}>
              <window.Icon.Search className="state-block__icon" />
              <h3 className="fr-h4">Aucun résultat</h3>
              <p>Essayez un autre terme, élargissez les niveaux ou retirez le filtre de tutelle.</p>
            </div>
          ) : results.map((e) => {
            const chain = window.U.tutelleChain(e.siren);
            return (
              <a key={e.siren} className="result" href={`#/fiche/${e.siren}`}>
                <div style={{ minWidth: 0 }}>
                  <div className="row-center wrap" style={{ gap: 8, marginBottom: 6 }}>
                    <window.LevelBadge level={e.level} unresolved={e.resolved === false} />
                    {e.category ? <span className="badge">{e.category}</span> : null}
                  </div>
                  <div className="fr-h4" style={{ marginBottom: 4 }}>{highlight(e.name, q)}</div>
                  <div className="breadcrumb fr-xs">
                    {chain.map((c, i) => <React.Fragment key={c.siren}>{i > 0 ? <span className="breadcrumb__sep">›</span> : null}<span>{c.acronym || c.name}</span></React.Fragment>)}
                  </div>
                </div>
                <div className="result__amount">
                  <div className="figure__value" style={{ fontSize: "1.25rem" }}>{window.U.euroCompact(e.cp_eur)}</div>
                  <div className="fr-xs text-mention">CP · exemple</div>
                </div>
              </a>
            );
          })}
        </div>
      </div>
    </div>
  );
}

window.RecherchePage = RecherchePage;
