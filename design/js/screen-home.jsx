/* Screen 1 — Accueil / Vue d'ensemble. → window.HomePage */

function HomePage({ go }) {
  const D = window.DATA;
  const nInst = D.entities.length;
  const nOperateurs = D.entities.filter((e) => e.parent_siren || e.level === "delegue").length;
  const nContrats = D.contracts.length;
  const budgetTotal = D.budgetFacts.filter((b) => !b.executed && b.exercice === 2025).reduce((s, b) => s + (b.amount_cp_eur || 0), 0);

  const figures = [
    { value: window.U.euroCompact(budgetTotal), label: "Crédits de paiement suivis (LFI 2025, missions au périmètre)", prov: "budget_plf_lfi", mil: "2025" },
    { value: nInst.toLocaleString("fr-FR"), label: "Institutions cartographiées", prov: "operateurs_etat", mil: "2025" },
    { value: nOperateurs.toLocaleString("fr-FR"), label: "Opérateurs et délégataires", prov: "operateurs_etat", mil: "2025" },
    { value: nContrats.toLocaleString("fr-FR"), label: "Contrats publics reliés", prov: "decp", mil: "2026" },
  ];

  const teaserLinks = window.buildFlowLinks("110044013");

  const actions = [
    { Icon: window.Icon.Graph, title: "Explorer le graphe", desc: "Naviguez le réseau des institutions : tutelles, financements, délégations.", to: "graphe", primary: true },
    { Icon: window.Icon.Search, title: "Rechercher une institution", desc: "Trouvez un ministère, un opérateur ou un titulaire par nom, niveau ou montant.", to: "recherche" },
    { Icon: window.Icon.Flow, title: "Suivre les flux", desc: "Du financeur public au titulaire, suivez où va l’argent.", to: "flux" },
  ];

  return (
    <div>
      {/* HERO */}
      <section className="hero">
        <div className="fr-container">
          <div className="hero__grid">
            <div>
              <span className="hero__eyebrow"><window.Icon.Pin style={{ width: 16, height: 16 }} /> Données publiques ouvertes · Licence Ouverte 2.0</span>
              <h1>Comprendre où va l’argent public, institution par institution.</h1>
              <p className="hero__lead">
                Choisissez une institution : voyez qui l’encadre, à quoi elle sert, combien elle reçoit et vers quels opérateurs son budget s’écoule — le tout relié aux sources officielles.
              </p>
              <div className="hero__cta">
                <button className="btn btn--primary btn--lg" onClick={() => go("graphe")}><window.Icon.Graph /> Explorer le graphe</button>
                <button className="btn btn--secondary btn--lg" onClick={() => go("recherche")}><window.Icon.Search /> Rechercher</button>
              </div>
              <div className="trust-strip" style={{ marginTop: 28 }}>
                <span className="trust-strip__item"><window.Icon.Check /> Données ouvertes</span>
                <span className="trust-strip__item"><window.Icon.Check /> Licences tracées</span>
                <span className="trust-strip__item"><window.Icon.Check /> Méthodologie publiée</span>
              </div>
            </div>

            {/* teaser viz */}
            <div className="card card--pad" style={{ background: "var(--blue-france-975)", borderColor: "var(--blue-france-925)" }}>
              <div className="row-center" style={{ justifyContent: "space-between", marginBottom: 4 }}>
                <span className="eyebrow" style={{ fontSize: "0.75rem" }}>Aperçu — principaux flux</span>
                <window.ExampleFlag>Exemple</window.ExampleFlag>
              </div>
              <div className="fr-sm" style={{ fontWeight: 600, color: "var(--grey-title)", marginBottom: 8 }}>Ministère de l’Enseignement supérieur et de la Recherche</div>
              <div style={{ background: "#fff", borderRadius: 6, border: "1px solid var(--blue-france-925)", padding: 8 }}>
                <window.Sankey links={teaserLinks} height={300} />
              </div>
              <button className="fr-link" style={{ marginTop: 12 }} onClick={() => go("flux/110044013")}>Voir tous les flux <window.Icon.Arrow style={{ width: 15, height: 15 }} /></button>
            </div>
          </div>
        </div>
      </section>

      {/* FIGURES */}
      <section className="fr-container" style={{ paddingBottom: 8 }}>
        <div className="figures">
          {figures.map((f, i) => (
            <div className="figure" key={i}>
              <div className="figure__value">{f.value}</div>
              <div className="figure__label">{f.label}</div>
              <div className="figure__prov"><window.ProvenanceBadge provId={f.prov} millesime={f.mil} onOpenSource={() => go("donnees")} /></div>
            </div>
          ))}
        </div>
        <p className="fr-xs text-mention" style={{ marginTop: 10 }}>Chiffres calculés sur le jeu de démonstration ; en production, ils portent sur l’ensemble du périmètre suivi. Voir <button className="fr-link" onClick={() => go("donnees")}>Données &amp; licences</button>.</p>
      </section>

      {/* WHAT YOU CAN DO */}
      <section className="fr-container" style={{ paddingBlock: "48px" }}>
        <div className="section-head">
          <div className="section-head__title">
            <span className="eyebrow">Ce que vous pouvez faire</span>
            <h2 className="fr-h2">Trois manières d’enquêter</h2>
          </div>
        </div>
        <div className="grid" style={{ gridTemplateColumns: "repeat(3, 1fr)" }}>
          {actions.map((a, i) => (
            <button key={i} className="tile" style={{ textAlign: "left", cursor: "pointer", flexDirection: "column", gap: 14 }} onClick={() => go(a.to)}>
              <a.Icon className="tile__icon" />
              <div>
                <div className="fr-h4" style={{ marginBottom: 6 }}>{a.title}</div>
                <p className="fr-sm text-mention">{a.desc}</p>
              </div>
              <span className="fr-link" style={{ marginTop: "auto" }}>{a.primary ? "Commencer" : "Ouvrir"} <window.Icon.Arrow style={{ width: 15, height: 15 }} /></span>
            </button>
          ))}
        </div>
      </section>

      {/* HOW IT WORKS / TRUST */}
      <section style={{ background: "var(--bg-alt)", borderTop: "1px solid var(--border-default)", borderBottom: "1px solid var(--border-default)" }}>
        <div className="fr-container" style={{ paddingBlock: 48 }}>
          <div className="grid" style={{ gridTemplateColumns: "1.1fr 1fr", gap: 48, alignItems: "center" }}>
            <div className="stack">
              <span className="eyebrow">Une donnée, une source</span>
              <h2 className="fr-h2">Chaque chiffre renvoie à sa source officielle</h2>
              <p className="fr-lead text-mention" style={{ fontSize: "1.05rem" }}>
                Nous distinguons toujours le <strong>voté</strong> de l’<strong>exécuté</strong>, et les <strong>autorisations d’engagement (AE)</strong> des <strong>crédits de paiement (CP)</strong>. Les entités non résolues sont signalées, pas masquées.
              </p>
              <div className="row wrap" style={{ gap: 8 }}>
                <span className="badge badge--blue">Voté vs exécuté</span>
                <span className="badge badge--blue">AE / CP</span>
                <span className="badge badge--blue">Millésime visible</span>
                <span className="badge">SIREN résolu / non résolu</span>
              </div>
              <button className="btn btn--tertiary" style={{ alignSelf: "flex-start", marginTop: 8 }} onClick={() => go("donnees")}><window.Icon.Scale /> Sources &amp; méthodologie</button>
            </div>
            <ul className="stack" style={{ gap: 12 }}>
              {D.SOURCES.slice(0, 4).map((s) => (
                <li key={s.id} className="card card--pad" style={{ padding: "16px 18px", flexDirection: "row", gap: 14, alignItems: "center" }}>
                  <window.Icon.Doc style={{ width: 22, height: 22, color: "var(--blue-france)", flex: "none" }} />
                  <div style={{ flex: 1 }}>
                    <div className="fr-sm" style={{ fontWeight: 600, color: "var(--grey-title)" }}>{s.publisher.split("—")[0].trim()}</div>
                    <div className="fr-xs text-mention">{s.licence} · millésime {s.millesime}</div>
                  </div>
                  <span className="badge badge--success">Ouverte</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>
    </div>
  );
}

window.HomePage = HomePage;
