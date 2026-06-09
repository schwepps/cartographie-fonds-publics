import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { ProvenanceBadge } from "../../lib/provenance/ProvenanceBadge";
import { allSources } from "../../lib/provenance/sources";
import { euroCompact } from "../../lib/format";
import {
  Arrow,
  Check,
  Doc,
  ExampleFlag,
  Figure,
  Flow,
  Graph,
  Pin,
  Sankey,
  Scale,
  Search,
} from "../../lib/ui";
import { useOverview } from "./useOverview";

const fr = (n: number) => n.toLocaleString("fr-FR");

interface FigureSpec {
  value: ReactNode;
  label: string;
  provenance: string;
  millesime: number;
}

interface ActionSpec {
  icon: ReactNode;
  title: string;
  desc: string;
  to: string;
  cta: string;
}

const ACTIONS: ActionSpec[] = [
  {
    icon: <Graph className="tile__icon" />,
    title: "Explorer le graphe",
    desc: "Naviguez le réseau des institutions : tutelles, financements, délégations.",
    to: "/graph",
    cta: "Commencer",
  },
  {
    icon: <Search className="tile__icon" />,
    title: "Rechercher une institution",
    desc: "Trouvez un ministère, un opérateur ou un titulaire par nom, niveau ou montant.",
    to: "/search",
    cta: "Ouvrir",
  },
  {
    icon: <Flow className="tile__icon" />,
    title: "Suivre les flux",
    desc: "Du financeur public au titulaire, suivez où va l’argent.",
    to: "/flux",
    cta: "Ouvrir",
  },
];

export default function HomePage() {
  const overview = useOverview();

  const figures: FigureSpec[] =
    overview.status === "ready"
      ? [
          {
            value: euroCompact(overview.figures.budgetCp),
            label: "Crédits de paiement suivis (LFI 2025, missions au périmètre)",
            provenance: "budget_plf_lfi",
            millesime: 2025,
          },
          {
            value: fr(overview.figures.institutions),
            label: "Institutions cartographiées",
            provenance: "operateurs_etat",
            millesime: 2025,
          },
          {
            value: fr(overview.figures.operateurs),
            label: "Opérateurs et délégataires",
            provenance: "operateurs_etat",
            millesime: 2025,
          },
          {
            value: fr(overview.figures.contrats),
            label: "Contrats publics reliés",
            provenance: "decp_commande_publique",
            millesime: 2026,
          },
        ]
      : [];

  return (
    <div>
      <section className="hero">
        <div className="fr-container">
          <div className="hero__grid">
            <div>
              <span className="hero__eyebrow">
                <Pin style={{ width: 16, height: 16 }} /> Données publiques ouvertes · Licence
                Ouverte 2.0
              </span>
              <h1>Comprendre où va l’argent public, institution par institution.</h1>
              <p className="hero__lead">
                Choisissez une institution : voyez qui l’encadre, à quoi elle sert, combien elle
                reçoit et vers quels opérateurs son budget s’écoule — le tout relié aux sources
                officielles.
              </p>
              <div className="hero__cta">
                <Link className="btn btn--primary btn--lg" to="/graph">
                  <Graph /> Explorer le graphe
                </Link>
                <Link className="btn btn--secondary btn--lg" to="/search">
                  <Search /> Rechercher
                </Link>
              </div>
              <div className="trust-strip" style={{ marginTop: 28 }}>
                <span className="trust-strip__item">
                  <Check /> Données ouvertes
                </span>
                <span className="trust-strip__item">
                  <Check /> Licences tracées
                </span>
                <span className="trust-strip__item">
                  <Check /> Méthodologie publiée
                </span>
              </div>
            </div>

            <div
              className="card card--pad"
              style={{
                background: "var(--blue-france-975)",
                borderColor: "var(--blue-france-925)",
              }}
            >
              <div
                className="row-center"
                style={{ justifyContent: "space-between", marginBottom: 4 }}
              >
                <span className="eyebrow" style={{ fontSize: "0.75rem" }}>
                  Aperçu — principaux flux
                </span>
                <ExampleFlag>Exemple</ExampleFlag>
              </div>
              <div
                className="fr-sm"
                style={{ fontWeight: 600, color: "var(--grey-title)", marginBottom: 8 }}
              >
                {overview.status === "ready" ? overview.teaser.name : "Flux de financement"}
              </div>
              <div
                style={{
                  background: "#fff",
                  borderRadius: 6,
                  border: "1px solid var(--blue-france-925)",
                  padding: 8,
                  minHeight: 316,
                }}
              >
                {overview.status === "ready" && overview.teaser.links.length > 0 ? (
                  <Sankey links={overview.teaser.links} height={300} />
                ) : null}
              </div>
              <Link className="fr-link" style={{ marginTop: 12 }} to="/flux">
                Voir tous les flux <Arrow style={{ width: 15, height: 15 }} />
              </Link>
            </div>
          </div>
        </div>
      </section>

      <section className="fr-container" style={{ paddingBottom: 8 }}>
        <div className="figures">
          {figures.map((f) => (
            <Figure
              key={f.label}
              value={f.value}
              label={f.label}
              provenance={<ProvenanceBadge provenanceId={f.provenance} millesime={f.millesime} />}
            />
          ))}
        </div>
        <p className="fr-xs text-mention" style={{ marginTop: 10 }}>
          Chiffres calculés sur le jeu de démonstration ; en production, ils portent sur l’ensemble
          du périmètre suivi. Voir{" "}
          <Link className="fr-link" to="/sources">
            Données &amp; licences
          </Link>
          .
        </p>
      </section>

      <section className="fr-container" style={{ paddingBlock: "48px" }}>
        <div className="section-head">
          <div className="section-head__title">
            <span className="eyebrow">Ce que vous pouvez faire</span>
            <h2 className="fr-h2">Trois manières d’enquêter</h2>
          </div>
        </div>
        <div className="grid" style={{ gridTemplateColumns: "repeat(3, 1fr)" }}>
          {ACTIONS.map((action) => (
            <Link
              key={action.to}
              className="tile"
              to={action.to}
              style={{ flexDirection: "column", gap: 14, textDecoration: "none" }}
            >
              {action.icon}
              <div>
                <div className="fr-h4" style={{ marginBottom: 6 }}>
                  {action.title}
                </div>
                <p className="fr-sm text-mention">{action.desc}</p>
              </div>
              <span className="fr-link" style={{ marginTop: "auto" }}>
                {action.cta} <Arrow style={{ width: 15, height: 15 }} />
              </span>
            </Link>
          ))}
        </div>
      </section>

      <section
        style={{
          background: "var(--bg-alt)",
          borderTop: "1px solid var(--border-default)",
          borderBottom: "1px solid var(--border-default)",
        }}
      >
        <div className="fr-container" style={{ paddingBlock: 48 }}>
          <div
            className="grid"
            style={{ gridTemplateColumns: "1.1fr 1fr", gap: 48, alignItems: "center" }}
          >
            <div className="stack">
              <span className="eyebrow">Une donnée, une source</span>
              <h2 className="fr-h2">Chaque chiffre renvoie à sa source officielle</h2>
              <p className="fr-lead text-mention">
                Nous distinguons toujours le <strong>voté</strong> de l’<strong>exécuté</strong>, et
                les <strong>autorisations d’engagement (AE)</strong> des{" "}
                <strong>crédits de paiement (CP)</strong>. Les entités non résolues sont signalées,
                pas masquées.
              </p>
              <div className="row wrap" style={{ gap: 8 }}>
                <span className="badge badge--blue">Voté vs exécuté</span>
                <span className="badge badge--blue">AE / CP</span>
                <span className="badge badge--blue">Millésime visible</span>
                <span className="badge">SIREN résolu / non résolu</span>
              </div>
              <Link
                className="btn btn--tertiary"
                to="/sources"
                style={{ alignSelf: "flex-start", marginTop: 8 }}
              >
                <Scale /> Sources &amp; méthodologie
              </Link>
            </div>
            <ul className="stack" style={{ gap: 12 }}>
              {allSources()
                .slice(0, 4)
                .map((source) => (
                  <li
                    key={source.id}
                    className="card card--pad"
                    style={{
                      padding: "16px 18px",
                      flexDirection: "row",
                      gap: 14,
                      alignItems: "center",
                    }}
                  >
                    <Doc
                      style={{ width: 22, height: 22, color: "var(--blue-france)", flex: "none" }}
                    />
                    <div style={{ flex: 1 }}>
                      <div
                        className="fr-sm"
                        style={{ fontWeight: 600, color: "var(--grey-title)" }}
                      >
                        {source.publisher.split("—")[0].trim()}
                      </div>
                      <div className="fr-xs text-mention">
                        {source.licence} · {source.cadence}
                      </div>
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
