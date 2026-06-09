/* Screen 3 — Fiche institution. → window.FichePage */

function MissionBars({ budget, exercice }) {
  const rows = budget.filter((b) => b.exercice === exercice && !b.executed);
  if (!rows.length) return null;
  const max = Math.max(...rows.map((r) => r.amount_cp_eur || 0));
  return (
    <div className="bars">
      {rows.map((r, i) => (
        <div className="bar-row" key={i}>
          <div className="bar-row__head">
            <span style={{ maxWidth: "70%" }}>{r.programme}</span>
            <span className="tnum" style={{ fontWeight: 600, color: "var(--grey-title)" }}>{window.U.euroCompact(r.amount_cp_eur)}</span>
          </div>
          <div className="bar-row__track"><div className="bar-row__fill" style={{ width: (r.amount_cp_eur / max * 100) + "%", background: window.U.seqColor(0.4 + 0.5 * (r.amount_cp_eur / max)) }}></div></div>
        </div>
      ))}
    </div>
  );
}

function TrendSpark({ budget }) {
  // aggregate CP by exercice (voté)
  const byYear = {};
  budget.forEach((b) => { const y = b.exercice; byYear[y] = (byYear[y] || 0) + (b.executed ? 0 : (b.amount_cp_eur || 0)); });
  const years = Object.keys(byYear).map(Number).sort();
  if (years.length < 2) return null;
  const max = Math.max(...years.map((y) => byYear[y]));
  const cur = years[years.length - 1];
  return (
    <div>
      <div className="spark" role="img" aria-label="Tendance pluriannuelle des crédits de paiement">
        {years.map((y) => (
          <div key={y} style={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "flex-end", gap: 4 }}>
            <div className={`spark__bar ${y === cur ? "is-current" : ""}`} style={{ height: (byYear[y] / max * 64) + "px" }} title={`${y} : ${window.U.euroCompact(byYear[y])}`}></div>
            <span className="fr-xs text-mention" style={{ textAlign: "center" }}>{y}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function FichePage({ params, go }) {
  const siren = params.siren;
  const e = window.U.entity(siren);
  if (!e) {
    return (
      <div className="page fr-container">
        <div className="state-block"><window.Icon.Warning className="state-block__icon" /><h2 className="fr-h3">Entité introuvable</h2><p>Aucune institution ne correspond au SIREN {siren}.</p><button className="btn btn--secondary" onClick={() => go("graphe")}>Retour au graphe</button></div>
      </div>
    );
  }
  const chain = window.U.tutelleChain(siren);
  const children = window.U.childrenOf(siren);
  const budget = window.U.budgetOf(siren);
  const exercices = [...new Set(budget.map((b) => b.exercice))].sort((a, b) => b - a);
  const lastEx = exercices[0];
  const voted = budget.filter((b) => b.exercice === lastEx && !b.executed);
  const executed = budget.filter((b) => b.exercice === lastEx && b.executed);
  const totalAeVoted = voted.reduce((s, b) => s + (b.amount_ae_eur || 0), 0);
  const totalCpVoted = voted.reduce((s, b) => s + (b.amount_cp_eur || 0), 0);
  const out = window.U.outflows(siren).sort((a, b) => b.amount_eur - a.amount_eur);
  const contracts = window.U.contractsOf(siren);
  const src = window.U.sourceOf(e.provenance);
  const m = window.U.levelMeta(e.level);

  // top titulaires (delegates)
  const titulaires = out.filter((o) => o.type === "delegates").slice(0, 5);
  const fundedOps = out.filter((o) => o.type === "funds").slice(0, 6);

  const budgetCols = [
    { key: "exercice", header: "Millésime", num: true },
    { key: "mission", header: "Mission" },
    { key: "programme", header: "Programme" },
    { key: "ae", header: "AE", num: true, render: (r) => <span className="tnum">{window.U.euroCompact(r.amount_ae_eur)}</span>, sortValue: (r) => r.amount_ae_eur || 0 },
    { key: "cp", header: "CP", num: true, render: (r) => <span className="tnum">{window.U.euroCompact(r.amount_cp_eur)}</span>, sortValue: (r) => r.amount_cp_eur || 0 },
    { key: "status", header: "Statut", render: (r) => <span className={`badge ${r.executed ? "badge--success" : "badge--blue"}`}>{r.executed ? "Exécuté" : "Voté"}</span> },
  ];

  return (
    <div className="page fr-container">
      <div className="page-head">
        <nav className="breadcrumb" aria-label="Fil d’Ariane">
          <a href="#/accueil">Accueil</a><span className="breadcrumb__sep">›</span>
          <a href="#/graphe">Graphe</a><span className="breadcrumb__sep">›</span>
          {chain.map((c, i) => (
            <React.Fragment key={c.siren}>
              {i > 0 ? <span className="breadcrumb__sep">›</span> : null}
              {c.siren === siren ? <span aria-current="page">{c.acronym || c.name}</span> : <a href={`#/fiche/${c.siren}`}>{c.acronym || c.name}</a>}
            </React.Fragment>
          ))}
        </nav>
      </div>

      {/* identity */}
      <div className="identity-head" style={{ marginBottom: 28 }}>
        <div style={{ maxWidth: "62ch" }}>
          <div className="row-center wrap" style={{ gap: 8, marginBottom: 12 }}>
            <window.LevelBadge level={e.level} unresolved={e.resolved === false} />
            {e.category ? <span className="badge">{e.category}</span> : null}
            <window.ExampleFlag>Exemple</window.ExampleFlag>
          </div>
          <h1 className="fr-h1" style={{ marginBottom: 10 }}>{e.name}</h1>
          <dl className="kv" style={{ maxWidth: 520 }}>
            <dt>SIREN</dt>
            <dd>{e.resolved === false ? <span className="text-mention">non résolu <button className="fr-link" title="Pourquoi ?">— pourquoi ?</button></span> : <span className="mono">{e.siren}</span>}</dd>
            <dt>Tutelle</dt>
            <dd>{e.parent_siren ? <a className="fr-link" href={`#/fiche/${e.parent_siren}`}>{window.U.nameOf(e.parent_siren)}</a> : <span className="text-mention">Administration centrale (sans tutelle)</span>}</dd>
          </dl>
          {e.resolved === false ? (
            <div className="callout callout--warning" style={{ marginTop: 16, padding: "12px 16px" }}>
              <p className="fr-sm"><strong>SIREN non résolu.</strong> Les listes d’opérateurs publient rarement le SIREN ; le rapprochement avec la base SIRENE n’a pas abouti pour cette entité. Les montants restent rattachés par nom, avec une fiabilité moindre.</p>
            </div>
          ) : null}
        </div>
        <div className="row wrap" style={{ gap: 8, alignItems: "flex-start" }}>
          <button className="btn btn--secondary" onClick={() => go(`graphe?locate=${siren}`)}><window.Icon.Graph /> Voir dans le graphe</button>
          <button className="btn btn--primary" onClick={() => go(`flux/${chain[0].siren}`)}><window.Icon.Flow /> Flux</button>
        </div>
      </div>

      <div className="sheet-grid">
        {/* LEFT: budget + relations */}
        <div className="stack" style={{ gap: 32 }}>
          {/* budget */}
          <section>
            <div className="section-head" style={{ marginBottom: 16 }}>
              <div className="section-head__title"><span className="eyebrow">Budget</span><h2 className="fr-h3">Crédits — exercice {lastEx || "n.d."}</h2></div>
            </div>
            {budget.length ? (
              <React.Fragment>
                <div className="grid" style={{ gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 20 }}>
                  <div className="figure" style={{ borderTopColor: "var(--niv-etat)" }}>
                    <div className="fr-xs text-mention" style={{ textTransform: "uppercase", letterSpacing: ".04em" }}>Autorisations d’engagement (AE) · voté</div>
                    <div className="figure__value" style={{ fontSize: "1.7rem" }}>{window.U.euroCompact(totalAeVoted)}</div>
                  </div>
                  <div className="figure">
                    <div className="fr-xs text-mention" style={{ textTransform: "uppercase", letterSpacing: ".04em" }}>Crédits de paiement (CP) · voté</div>
                    <div className="figure__value" style={{ fontSize: "1.7rem" }}>{window.U.euroCompact(totalCpVoted)}</div>
                  </div>
                </div>
                <div className="grid" style={{ gridTemplateColumns: "1.4fr 1fr", gap: 28, alignItems: "start" }}>
                  <div>
                    <div className="fr-sm" style={{ fontWeight: 600, marginBottom: 10 }}>Répartition par programme (CP voté {lastEx})</div>
                    <MissionBars budget={budget} exercice={lastEx} />
                  </div>
                  {exercices.length > 1 ? (
                    <div>
                      <div className="fr-sm" style={{ fontWeight: 600, marginBottom: 10 }}>Tendance pluriannuelle (CP)</div>
                      <TrendSpark budget={budget} />
                    </div>
                  ) : null}
                </div>
                <details style={{ marginTop: 20 }}>
                  <summary className="fr-link" style={{ cursor: "pointer" }}>Détail par mission / programme (AE/CP, voté &amp; exécuté)</summary>
                  <div style={{ marginTop: 12 }}>
                    <window.DataTable caption={`Crédits budgétaires — ${e.name}`} columns={budgetCols} rows={budget.map((b, i) => ({ ...b, i }))} getRowKey={(r) => r.i} />
                  </div>
                </details>
                <div style={{ marginTop: 10 }}><window.ProvenanceBadge provId="budget_plf_lfi" millesime={lastEx} onOpenSource={() => go("donnees")} /></div>
              </React.Fragment>
            ) : (
              <div className="callout"><p className="fr-sm">Aucun crédit budgétaire directement attribué à cette entité dans le périmètre suivi. Son financement apparaît côté <button className="fr-link" onClick={() => go(`flux/${chain[0].siren}`)}>flux</button> (subvention de sa tutelle).</p></div>
            )}
          </section>

          {/* où va son argent (mini flux) */}
          {out.length ? (
            <section>
              <div className="section-head" style={{ marginBottom: 16 }}>
                <div className="section-head__title"><span className="eyebrow">Suivre l’argent</span><h2 className="fr-h3">Où va son argent</h2></div>
                <button className="fr-link" onClick={() => go(`flux/${chain[0].siren}`)}>Diagramme complet <window.Icon.Arrow style={{ width: 15, height: 15 }} /></button>
              </div>
              <div className="bars">
                {out.slice(0, 6).map((o, i) => {
                  const max = out[0].amount_eur;
                  return (
                    <div className="bar-row" key={i}>
                      <div className="bar-row__head">
                        <a className="fr-link" href={`#/fiche/${o.target_siren}`}>{window.U.nameOf(o.target_siren)}</a>
                        <span className="tnum" style={{ fontWeight: 600, color: "var(--grey-title)" }}>{window.U.euroCompact(o.amount_eur)}</span>
                      </div>
                      <div className="bar-row__track"><div className="bar-row__fill" style={{ width: (o.amount_eur / max * 100) + "%", background: o.type === "delegates" ? "var(--niv-delegue)" : "var(--seq-5)" }}></div></div>
                    </div>
                  );
                })}
              </div>
            </section>
          ) : null}

          {/* contracts / titulaires */}
          {contracts.length ? (
            <section>
              <div className="section-head" style={{ marginBottom: 16 }}>
                <div className="section-head__title"><span className="eyebrow">Commande publique</span><h2 className="fr-h3">Principaux titulaires</h2></div>
              </div>
              <window.DataTable
                caption={`Contrats (DECP) — ${e.name}`}
                columns={[
                  { key: "objet", header: "Objet" },
                  { key: "titulaire", header: e.siren === contracts[0].acheteur_siren ? "Titulaire" : "Acheteur", render: (r) => { const other = r.acheteur_siren === siren ? r.titulaire_siren : r.acheteur_siren; const o = window.U.entity(other); return <a className="fr-link" href={`#/fiche/${other}`}>{o ? o.name : other}</a>; } },
                  { key: "nature", header: "Nature", render: (r) => <span className="tag tag--sm">{r.nature === "marche" ? "Marché" : "Concession"}</span> },
                  { key: "montant", header: "Montant", num: true, render: (r) => <span className="tnum">{window.U.euroFull(r.montant_eur)}</span>, sortValue: (r) => r.montant_eur },
                  { key: "exercice", header: "Millésime", num: true, render: (r) => r.exercice },
                ]}
                rows={contracts.map((c, i) => ({ ...c, i }))}
                getRowKey={(r) => r.i}
              />
              <div style={{ marginTop: 10 }}><window.ProvenanceBadge provId="decp" millesime={2026} onOpenSource={() => go("donnees")} /></div>
            </section>
          ) : null}
        </div>

        {/* RIGHT: relations rail */}
        <aside className="stack" style={{ gap: 20 }}>
          <div className="card card--pad card__top-border">
            <div className="fr-xs text-mention" style={{ textTransform: "uppercase", letterSpacing: ".04em", marginBottom: 8 }}>Chaîne de tutelle</div>
            <ol style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {chain.map((c, i) => (
                <li key={c.siren} className="row-center" style={{ gap: 8, paddingLeft: i * 14 }}>
                  {i > 0 ? <span className="text-mention">└</span> : null}
                  <window.LevelShape level={c.level} size={11} />
                  {c.siren === siren ? <strong className="fr-sm">{c.name}</strong> : <a className="fr-link fr-sm" href={`#/fiche/${c.siren}`}>{c.name}</a>}
                </li>
              ))}
            </ol>
          </div>

          {children.length ? (
            <div className="card card--pad">
              <div className="fr-xs text-mention" style={{ textTransform: "uppercase", letterSpacing: ".04em", marginBottom: 8 }}>Opérateurs sous tutelle ({children.length})</div>
              <div className="row wrap" style={{ gap: 6 }}>
                {children.map((c) => <window.Chip key={c.siren} sm level={c.level} onClick={() => go(`fiche/${c.siren}`)}>{c.acronym || c.name}</window.Chip>)}
              </div>
            </div>
          ) : null}

          {fundedOps.length ? (
            <div className="card card--pad">
              <div className="fr-xs text-mention" style={{ textTransform: "uppercase", letterSpacing: ".04em", marginBottom: 8 }}>Opérateurs financés</div>
              <div className="row wrap" style={{ gap: 6 }}>
                {fundedOps.map((o) => <window.Chip key={o.target_siren} sm level={window.U.entity(o.target_siren).level} onClick={() => go(`fiche/${o.target_siren}`)}>{window.U.entity(o.target_siren).acronym || window.U.nameOf(o.target_siren)}</window.Chip>)}
              </div>
            </div>
          ) : null}

          <div className="card card--pad" style={{ background: "var(--bg-alt)" }}>
            <div className="fr-xs text-mention" style={{ textTransform: "uppercase", letterSpacing: ".04em", marginBottom: 8 }}>Provenance</div>
            <dl className="kv" style={{ gridTemplateColumns: "90px 1fr", fontSize: "0.8125rem" }}>
              <dt>Source</dt><dd>{src ? src.publisher.split("—")[0].trim() : "—"}</dd>
              <dt>Licence</dt><dd>{src ? src.licence : "—"}</dd>
              <dt>Millésime</dt><dd>{src ? src.millesime : "—"}</dd>
              <dt>Données au</dt><dd>{src ? src.updated : "—"}</dd>
            </dl>
            <button className="fr-link fr-sm" style={{ marginTop: 10 }} onClick={() => go("donnees")}>Détail de la source <window.Icon.Arrow style={{ width: 14, height: 14 }} /></button>
          </div>
        </aside>
      </div>
    </div>
  );
}

window.FichePage = FichePage;
