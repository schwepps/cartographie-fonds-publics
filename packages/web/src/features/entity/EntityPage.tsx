import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router-dom";
import { DataTableFallback } from "../../lib/a11y/DataTableFallback";
import { ProvenanceBadge } from "../../lib/provenance/ProvenanceBadge";
import type { EdgeRow } from "./types";
import { useEntitySheet } from "./useEntitySheet";

const amountFormatter = new Intl.NumberFormat("fr-FR");

function formatAmount(amount: number | null): string {
  return amount == null ? "—" : amountFormatter.format(amount);
}

function counterpartSiren(edge: EdgeRow, siren: string): string {
  return edge.source_siren === siren ? edge.target_siren : edge.source_siren;
}

/**
 * Minimal entity sheet — identity + the relationships the entity participates in,
 * each row annotated with a `ProvenanceBadge` (source · licence · millésime). The
 * relationships render through `DataTableFallback`, the accessible table that
 * graphical views must also provide. This is the surface FSC-28 requires provenance
 * to be visible on; the rich graph/flows sheet is a separate lane.
 */
export default function EntityPage() {
  const { t } = useTranslation();
  const { siren = "" } = useParams<{ siren: string }>();
  const state = useEntitySheet(siren);

  if (state.status === "loading") {
    return <p className="fr-text--lead">{t("entity.loading")}</p>;
  }
  if (state.status === "error") {
    return (
      <p role="alert" className="fr-text-default--error">
        {t("entity.error")}
      </p>
    );
  }
  if (!state.entity) {
    return <p className="fr-text--lead">{t("entity.notFound", { siren })}</p>;
  }

  const { entity, edges } = state;
  const columns = [
    { key: "type", header: t("entity.col.type") },
    { key: "counterpart", header: t("entity.col.counterpart") },
    { key: "amount", header: t("entity.col.amount") },
    { key: "exercice", header: t("entity.col.exercice") },
    { key: "provenance", header: t("entity.col.provenance") },
  ];
  const rows: Array<Record<string, ReactNode>> = edges.map((edge) => {
    const counterpart = counterpartSiren(edge, siren);
    return {
      type: edge.type,
      counterpart: <Link to={`/entity/${counterpart}`}>{counterpart}</Link>,
      amount: formatAmount(edge.amount_eur),
      exercice: edge.exercice ?? "—",
      provenance: edge.provenance ? (
        <ProvenanceBadge provenanceId={edge.provenance} millesime={edge.exercice} />
      ) : (
        "—"
      ),
    };
  });

  return (
    <section>
      <h1 className="fr-h1">{entity.name}</h1>
      <ul className="fr-text--sm">
        <li>
          {t("entity.siren")} : {entity.siren}
        </li>
        <li>
          {t("entity.level")} : {entity.level}
        </li>
        {entity.category ? (
          <li>
            {t("entity.category")} : {entity.category}
          </li>
        ) : null}
        {entity.provenance ? (
          <li>
            {t("entity.source")} : <ProvenanceBadge provenanceId={entity.provenance} />
          </li>
        ) : null}
      </ul>

      <h2 className="fr-h2">{t("entity.figuresTitle")}</h2>
      {edges.length === 0 ? (
        <p>{t("entity.empty")}</p>
      ) : (
        <DataTableFallback caption={t("entity.tableCaption")} columns={columns} rows={rows} />
      )}
    </section>
  );
}
