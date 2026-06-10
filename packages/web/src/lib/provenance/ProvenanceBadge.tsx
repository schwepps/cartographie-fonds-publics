import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { getSource } from "./sources";

export interface ProvenanceBadgeProps {
  /** The `edges.provenance` value — a source id from the registry. */
  provenanceId: string;
  /** Millésime of the figure (e.g. `edges.exercice`), shown when present. */
  millesime?: number | null;
}

/**
 * Inline attribution for a single figure: source · licence · millésime, linking to
 * the matching entry on the sources page. Values are read from the registry, never
 * hardcoded. An explicit `aria-label` gives assistive tech the full provenance in
 * one phrase rather than three disconnected fragments.
 */
export function ProvenanceBadge({ provenanceId, millesime }: ProvenanceBadgeProps) {
  const { t } = useTranslation();
  const source = getSource(provenanceId);

  if (!source) {
    return (
      <span className="fr-sm text-error">{t("provenance.unknown", { id: provenanceId })}</span>
    );
  }

  const millesimeText = millesime == null ? "" : t("provenance.ariaMillesime", { millesime });
  const ariaLabel = t("provenance.aria", {
    publisher: source.publisher,
    licence: source.licence,
    millesime: millesimeText,
  });

  return (
    <span className="prov">
      <span className="prov__dot" aria-hidden="true" />
      <Link
        to={`/sources#source-${source.id}`}
        aria-label={ariaLabel}
        title={t("provenance.seeSources")}
      >
        {source.publisher} · {source.licence}
        {millesime == null ? null : ` · ${t("provenance.millesime")} ${millesime}`}
      </Link>
    </span>
  );
}
