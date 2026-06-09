/* Screen 6 — Données & licences. → window.DonneesPage */

function DonneesPage({ go }) {
  const sources = window.DATA.SOURCES;
  const cols = [
    { key: "publisher", header: "Producteur / source", render: (r) => <div><div style={{ fontWeight: 600, color: "var(--grey-title)" }}>{r.publisher}</div><div className="fr-xs text-mention">{r.description}</div></div> },
    { key: "licence", header: "Licence", render: (r) => <span className="badge badge--success">{r.licence}</span> },
    { key: "millesime", header: "Millésime", num: true },
    { key: "cadence", header: "Mise à jour" },
    { key: "updated", header: "Données au", render: (r) => <span className="mono fr-xs">{r.updated}</span> },
  ];

  const notes = [
    { t: "Voté vs exécuté", d: "Les crédits « votés » proviennent de la loi de finances (PLF/LFI) ; l’« exécuté » est constaté en fin d’exercice. Nous ne mélangeons jamais les deux et indiquons toujours le statut." },
    { t: "AE et CP", d: "Les autorisations d’engagement (AE) couvrent l’engagement juridique pluriannuel ; les crédits de paiement (CP) couvrent les décaissements de l’année. Un programme peut afficher des AE et des CP très différents." },
    { t: "Double-comptage", d: "Un même euro peut apparaître à plusieurs niveaux (subvention d’État reversée par un opérateur, cofinancement par une collectivité). Les totaux agrégés sont donc des ordres de grandeur, jamais des sommes consolidées." },
    { t: "Entités non résolues", d: "Les listes d’opérateurs et certaines données de marchés ne publient pas de SIREN. Le rapprochement avec SIRENE échoue alors : ces entités sont signalées « SIREN non résolu » et leurs montants rattachés par nom, avec une fiabilité moindre." },
    { t: "Périmètre", d: "Le jeu de démonstration couvre une tranche État-central (Culture, ESR, Travail) et quelques entités sociales et locales pour illustrer les quatre niveaux. Le périmètre de production est défini par le registre des sources." },
  ];

  return (
    <div className="page fr-container">
      <div className="page-head">
        <nav className="breadcrumb" aria-label="Fil d’Ariane"><a href="#/accueil">Accueil</a><span className="breadcrumb__sep">›</span><span>Données &amp; licences</span></nav>
        <div className="section-head" style={{ marginTop: 12, marginBottom: 0 }}>
          <div className="section-head__title"><span className="eyebrow">Transparence</span><h1 className="fr-h1">Données &amp; licences</h1></div>
        </div>
        <p className="fr-lead" style={{ marginTop: 12, maxWidth: "72ch" }}>
          Toutes les données proviennent de sources publiques ouvertes. Chaque figure de l’application renvoie à l’une des sources ci-dessous. Réutilisation sous Licence Ouverte / Etalab 2.0 — attribution au producteur indiqué.
        </p>
      </div>

      <div className="notice" style={{ marginBottom: 24 }}>
        <div className="fr-container" style={{ padding: 0 }}>
          <div className="row-center" style={{ gap: 10 }}>
            <window.Icon.Info style={{ width: 18, height: 18, color: "var(--info)", flex: "none" }} />
            <span className="fr-sm">Registre des sources à jour au <strong>9 juin 2026</strong>. Les sources évoluent : rien n’est codé en dur, tout est résolu depuis le registre.</span>
          </div>
        </div>
      </div>

      <window.DataTable caption="Sources de données et licences" columns={cols} rows={sources.map((s, i) => ({ ...s, i }))} getRowKey={(r) => r.id} />

      <h2 className="fr-h2" style={{ marginTop: 48, marginBottom: 8 }}>Notes de méthodologie</h2>
      <p className="fr-sm text-mention" style={{ marginBottom: 20, maxWidth: "70ch" }}>Pour ne jamais laisser croire à une précision que nous n’avons pas, voici les principales limites à garder en tête.</p>
      <div className="grid" style={{ gridTemplateColumns: "repeat(2, 1fr)" }}>
        {notes.map((n, i) => (
          <div key={i} className="card card--pad" style={{ borderLeft: "4px solid var(--blue-france)" }}>
            <div className="fr-h4" style={{ marginBottom: 6 }}>{n.t}</div>
            <p className="fr-sm">{n.d}</p>
          </div>
        ))}
        <div className="card card--pad" style={{ background: "var(--blue-france-975)", borderColor: "var(--blue-france-925)", justifyContent: "center" }}>
          <window.Icon.Shield style={{ width: 28, height: 28, color: "var(--blue-france)", marginBottom: 10 }} />
          <div className="fr-h4" style={{ marginBottom: 6 }}>Accessibilité &amp; code</div>
          <p className="fr-sm">Interface conçue pour viser le RGAA / WCAG 2.1 AA : navigation clavier, équivalents tabulaires, contrastes et indices non colorés. Code sous licence AGPL-3.0.</p>
          <div className="row wrap" style={{ gap: 8, marginTop: 12 }}>
            <span className="badge badge--blue">RGAA visé</span>
            <span className="badge badge--blue">AGPL-3.0</span>
            <span className="badge badge--blue">Reduced-motion</span>
          </div>
        </div>
      </div>

      <div className="callout" style={{ marginTop: 32 }}>
        <div className="row-center wrap" style={{ justifyContent: "space-between", gap: 16 }}>
          <div>
            <strong className="fr-h4" style={{ color: "var(--grey-title)" }}>Une source a changé ?</strong>
            <p className="fr-sm" style={{ marginTop: 4 }}>Signalez une source obsolète ou une erreur de rattachement — le registre est ouvert et versionné.</p>
          </div>
          <a className="btn btn--secondary" href="https://www.etalab.gouv.fr/licence-ouverte-open-licence/" target="_blank" rel="noopener"><window.Icon.External /> Licence Ouverte 2.0</a>
        </div>
      </div>
    </div>
  );
}

window.DonneesPage = DonneesPage;
