import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ProvenanceBadge } from "../../lib/provenance/ProvenanceBadge";
import { IS_DEMO } from "../../lib/config";
import { euroCompact } from "../../lib/format";
import { LEVELS, type Level } from "../../lib/levels";
import {
  Arrow,
  Breadcrumb,
  ExampleFlag,
  LevelShape,
  MethodologyNote,
  Sankey,
  StateBlock,
} from "../../lib/ui";
import { usePerimetreData } from "./usePerimetreData";

/** What each level's headline measures — surfaced so the figures are read in their own universe. */
const BASIS: Record<Level, string> = {
  state: "Crédits de paiement votés (LOLF)",
  local: "Dépenses réalisées (M57/M14)",
  social: "Prestations par branche — module agrégé (LFSS)",
  delegated: "Montants de marchés et concessions (DECP)",
};

export default function PerimetrePage() {
  const { t } = useTranslation();
  const perimetre = usePerimetreData();

  if (perimetre.status === "loading") {
    return (
      <div className="page fr-container">
        <StateBlock title="Chargement de l’aperçu du périmètre…" />
      </div>
    );
  }
  if (perimetre.status === "error") {
    return (
      <div className="page fr-container">
        <StateBlock variant="error" title="Aperçu du périmètre indisponible">
          Impossible de charger les chiffres. Réessayez plus tard.
        </StateBlock>
      </div>
    );
  }

  const { figures, teaser } = perimetre;

  return (
    <div className="page fr-container">
      <div className="page-head">
        <Breadcrumb items={[{ label: "Accueil", to: "/" }, { label: "Aperçu du périmètre" }]} />
        <h1 className="fr-h1">Aperçu du périmètre</h1>
        <p className="fr-lead text-mention" style={{ maxWidth: "62ch" }}>
          Une vue d’ensemble des quatre sphères de la dépense publique — État, collectivités,
          sécurité sociale et opérateurs délégués. Chaque chiffre renvoie à sa source. Les sphères
          relèvent d’univers comptables distincts : ce sont des ordres de grandeur, jamais une somme
          consolidée.
        </p>
      </div>

      <div className="figures">
        {figures.map((fig) => {
          const meta = LEVELS[fig.level];
          return (
            <div key={fig.level} className="figure" style={{ borderTopColor: meta.color }}>
              <div className="row-center" style={{ gap: 8, marginBottom: 6 }}>
                <LevelShape level={fig.level} size={14} />
                <span className="eyebrow" style={{ fontSize: "0.75rem" }}>
                  {meta.label}
                </span>
              </div>
              <div className="figure__value tnum">{euroCompact(fig.total)}</div>
              <div className="figure__label">{BASIS[fig.level]}</div>
              <div className="figure__prov" style={{ justifyContent: "space-between" }}>
                <ProvenanceBadge provenanceId={fig.provenanceId} millesime={fig.millesime} />
                <Link
                  className="fr-link"
                  to={fig.detailTo}
                  aria-label={`Détail du périmètre ${meta.label}`}
                >
                  Explorer <Arrow style={{ width: 15, height: 15 }} />
                </Link>
              </div>
            </div>
          );
        })}
      </div>

      <div className="stack" style={{ gap: 12, marginTop: 24, maxWidth: "78ch" }}>
        <MethodologyNote>{t("methodology.perimeter")}</MethodologyNote>
        <MethodologyNote>{t("methodology.aggregatedModule")}</MethodologyNote>
      </div>

      <section style={{ marginTop: 40 }}>
        <div className="section-head">
          <div className="section-head__title">
            <span className="eyebrow">Comment l’argent circule</span>
            <h2 className="fr-h2">Aperçu des flux de financement</h2>
          </div>
          <ExampleFlag>Exemple</ExampleFlag>
        </div>
        <div
          className="card card--pad"
          style={{ background: "#fff", borderColor: "var(--border-default)", minHeight: 332 }}
        >
          {teaser.links.length > 0 ? (
            <Sankey
              links={teaser.links}
              height={320}
              ariaLabel={`Aperçu des principaux flux de financement de ${teaser.name}${IS_DEMO ? " (montants d’exemple)" : ""}. Détail complet et équivalent tabulaire sur la page Flux de financement.`}
            />
          ) : (
            <StateBlock title="Aucun flux disponible" />
          )}
          <Link className="fr-link" style={{ marginTop: 12 }} to="/flux">
            Voir tous les flux <Arrow style={{ width: 15, height: 15 }} />
          </Link>
        </div>
      </section>
    </div>
  );
}
