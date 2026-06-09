import type { ReactNode } from "react";
import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router-dom";
import { DataTableFallback } from "../../lib/a11y/DataTableFallback";
import { ProvenanceBadge } from "../../lib/provenance/ProvenanceBadge";
import { counterpartSiren, useEntitySheet } from "./useEntitySheet";

/**
 * Entity sheet — identity (with its tutelle), the budget facts attributed to it, and the
 * relationships it participates in. Counterparts and the tutelle render by name (not bare SIRENs)
 * for readability; each relationship carries a `ProvenanceBadge` (source · licence · millésime),
 * and the tables render through `DataTableFallback`, the accessible surface graphical views must
 * also provide. Budget facts have no provenance column, so they render without a badge.
 */
export default function EntityPage() {
  const { t, i18n } = useTranslation();
  const { siren = "" } = useParams<{ siren: string }>();
  const state = useEntitySheet(siren);

  // Format amounts in the active UI language (the app ships fr + en and keeps <html lang> in sync).
  const amountFormatter = useMemo(() => new Intl.NumberFormat(i18n.language), [i18n.language]);
  const formatAmount = (amount: number | null): string =>
    amount == null ? "—" : amountFormatter.format(amount);

  if (state.status === "loading") {
    return (
      <div className="fr-container legacy-page">
        <p className="fr-lead">{t("entity.loading")}</p>
      </div>
    );
  }
  if (state.status === "error") {
    return (
      <div className="fr-container legacy-page">
        <p role="alert" className="text-error">
          {t("entity.error")}
        </p>
      </div>
    );
  }
  if (!state.entity) {
    return (
      <div className="fr-container legacy-page">
        <p className="fr-lead">{t("entity.notFound", { siren })}</p>
      </div>
    );
  }

  const { entity, edges, budgetFacts, nameBySiren } = state;
  const nameOf = (target: string): string => nameBySiren.get(target) ?? target;

  const relationshipColumns = [
    { key: "type", header: t("entity.col.type") },
    { key: "counterpart", header: t("entity.col.counterpart") },
    { key: "amount", header: t("entity.col.amount") },
    { key: "exercice", header: t("entity.col.exercice") },
    { key: "provenance", header: t("entity.col.provenance") },
  ];
  const relationshipRows: Array<Record<string, ReactNode>> = edges.map((edge) => {
    const counterpart = counterpartSiren(edge, siren);
    return {
      type: edge.type,
      counterpart: <Link to={`/entity/${counterpart}`}>{nameOf(counterpart)}</Link>,
      amount: formatAmount(edge.amount_eur),
      exercice: edge.exercice ?? "—",
      provenance: edge.provenance ? (
        <ProvenanceBadge provenanceId={edge.provenance} millesime={edge.exercice} />
      ) : (
        "—"
      ),
    };
  });

  const budgetColumns = [
    { key: "exercice", header: t("entity.budget.col.exercice") },
    { key: "mission", header: t("entity.budget.col.mission") },
    { key: "programme", header: t("entity.budget.col.programme") },
    { key: "ae", header: t("entity.budget.col.ae") },
    { key: "cp", header: t("entity.budget.col.cp") },
    { key: "status", header: t("entity.budget.col.status") },
  ];
  const budgetRows: Array<Record<string, ReactNode>> = budgetFacts.map((fact) => ({
    exercice: fact.exercice,
    mission: fact.mission ?? "—",
    programme: fact.programme ?? "—",
    ae: formatAmount(fact.amount_ae_eur),
    cp: formatAmount(fact.amount_cp_eur),
    status: fact.executed ? t("entity.budget.status.executed") : t("entity.budget.status.voted"),
  }));

  return (
    <section className="fr-container legacy-page">
      <h1 className="fr-h1">{entity.name}</h1>
      <ul className="fr-sm">
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
        {entity.parent_siren ? (
          <li>
            {t("entity.tutelle")} :{" "}
            <Link to={`/entity/${entity.parent_siren}`}>{nameOf(entity.parent_siren)}</Link>
          </li>
        ) : null}
        {entity.provenance ? (
          <li>
            {t("entity.source")} : <ProvenanceBadge provenanceId={entity.provenance} />
          </li>
        ) : null}
      </ul>

      <h2 className="fr-h2">{t("entity.budget.title")}</h2>
      {budgetFacts.length === 0 ? (
        <p>{t("entity.budget.empty")}</p>
      ) : (
        <DataTableFallback
          caption={t("entity.budget.tableCaption")}
          columns={budgetColumns}
          rows={budgetRows}
        />
      )}

      <h2 className="fr-h2">{t("entity.figuresTitle")}</h2>
      {edges.length === 0 ? (
        <p>{t("entity.empty")}</p>
      ) : (
        <DataTableFallback
          caption={t("entity.tableCaption")}
          columns={relationshipColumns}
          rows={relationshipRows}
        />
      )}
    </section>
  );
}
