import { allSources, registryUpdatedAt, type Source } from "../../lib/provenance/sources";
import { Breadcrumb, DataTable, External, Info, Shield, type DataTableColumn } from "../../lib/ui";

const NOTES: { title: string; body: string }[] = [
  {
    title: "Voté vs exécuté",
    body: "Les crédits « votés » proviennent de la loi de finances (PLF/LFI) ; l’« exécuté » est constaté en fin d’exercice. Nous ne mélangeons jamais les deux et indiquons toujours le statut.",
  },
  {
    title: "AE et CP",
    body: "Les autorisations d’engagement (AE) couvrent l’engagement juridique pluriannuel ; les crédits de paiement (CP) couvrent les décaissements de l’année. Un programme peut afficher des AE et des CP très différents.",
  },
  {
    title: "Double-comptage",
    body: "Un même euro peut apparaître à plusieurs niveaux (subvention d’État reversée par un opérateur, cofinancement par une collectivité). Les totaux agrégés sont des ordres de grandeur, jamais des sommes consolidées.",
  },
  {
    title: "Entités non résolues",
    body: "Les listes d’opérateurs et certaines données de marchés ne publient pas de SIREN. Le rapprochement avec SIRENE échoue alors : ces entités sont signalées « SIREN non résolu » et leurs montants rattachés par nom, avec une fiabilité moindre.",
  },
  {
    title: "Périmètre",
    body: "Le jeu de démonstration couvre une tranche État-central (Culture, ESR, Travail) et quelques entités sociales et locales pour illustrer les quatre niveaux. Le périmètre de production est défini par le registre des sources.",
  },
];

const columns: DataTableColumn<Source>[] = [
  {
    key: "publisher",
    header: "Producteur / source",
    render: (r) => (
      <div>
        <div style={{ fontWeight: 600, color: "var(--grey-title)" }}>{r.publisher}</div>
        <div className="fr-xs text-mention">{r.description}</div>
      </div>
    ),
    sortValue: (r) => r.publisher,
  },
  {
    key: "licence",
    header: "Licence",
    render: (r) => <span className="badge badge--success">{r.licence}</span>,
  },
  { key: "cadence", header: "Mise à jour", sortValue: (r) => r.cadence },
];

export default function SourcesPage() {
  const sources = allSources();

  return (
    <div className="page fr-container">
      <div className="page-head">
        <Breadcrumb items={[{ label: "Accueil", to: "/" }, { label: "Données & licences" }]} />
        <div className="section-head" style={{ marginTop: 12, marginBottom: 0 }}>
          <div className="section-head__title">
            <span className="eyebrow">Transparence</span>
            <h1 className="fr-h1">Données &amp; licences</h1>
          </div>
        </div>
        <p className="fr-lead" style={{ marginTop: 12, maxWidth: "72ch" }}>
          Toutes les données proviennent de sources publiques ouvertes. Chaque figure de
          l’application renvoie à l’une des sources ci-dessous. Réutilisation sous Licence Ouverte /
          Etalab 2.0 — attribution au producteur indiqué.
        </p>
      </div>

      <div className="notice" style={{ marginBottom: 24 }}>
        <div className="row-center" style={{ gap: 10 }}>
          <Info style={{ width: 18, height: 18, color: "var(--info)", flex: "none" }} />
          <span className="fr-sm">
            Registre des sources à jour au <strong>{registryUpdatedAt}</strong>. Les sources
            évoluent : rien n’est codé en dur, tout est résolu depuis le registre.
          </span>
        </div>
      </div>

      <DataTable
        caption="Sources de données et licences"
        columns={columns}
        rows={sources}
        getRowKey={(r) => r.id}
        getRowId={(r) => `source-${r.id}`}
      />

      <h2 className="fr-h2" style={{ marginTop: 48, marginBottom: 8 }}>
        Notes de méthodologie
      </h2>
      <p className="fr-sm text-mention" style={{ marginBottom: 20, maxWidth: "70ch" }}>
        Pour ne jamais laisser croire à une précision que nous n’avons pas, voici les principales
        limites à garder en tête.
      </p>
      <div className="grid" style={{ gridTemplateColumns: "repeat(2, 1fr)" }}>
        {NOTES.map((n) => (
          <div
            key={n.title}
            className="card card--pad"
            style={{ borderLeft: "4px solid var(--blue-france)" }}
          >
            <div className="fr-h4" style={{ marginBottom: 6 }}>
              {n.title}
            </div>
            <p className="fr-sm">{n.body}</p>
          </div>
        ))}
        <div
          className="card card--pad"
          style={{
            background: "var(--blue-france-975)",
            borderColor: "var(--blue-france-925)",
            justifyContent: "center",
          }}
        >
          <Shield
            style={{ width: 28, height: 28, color: "var(--blue-france)", marginBottom: 10 }}
          />
          <div className="fr-h4" style={{ marginBottom: 6 }}>
            Accessibilité &amp; code
          </div>
          <p className="fr-sm">
            Interface conçue pour viser le RGAA / WCAG 2.1 AA : navigation clavier, équivalents
            tabulaires, contrastes et indices non colorés. Code sous licence AGPL-3.0.
          </p>
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
            <strong className="fr-h4" style={{ color: "var(--grey-title)" }}>
              Une source a changé ?
            </strong>
            <p className="fr-sm" style={{ marginTop: 4 }}>
              Signalez une source obsolète ou une erreur de rattachement — le registre est ouvert et
              versionné.
            </p>
          </div>
          <a
            className="btn btn--secondary"
            href="https://www.etalab.gouv.fr/licence-ouverte-open-licence/"
            target="_blank"
            rel="noopener noreferrer"
          >
            <External /> Licence Ouverte 2.0
          </a>
        </div>
      </div>
    </div>
  );
}
