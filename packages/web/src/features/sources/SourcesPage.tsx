import { useTranslation } from "react-i18next";
import { allSources, registryUpdatedAt } from "../../lib/provenance/sources";

/**
 * Global "Données & licences" page: lists every registry source with its publisher,
 * licence and cadence — the Licence Ouverte attribution surface. Each row carries a
 * `source-<id>` anchor that `ProvenanceBadge` links to. Read from the registry, not
 * hardcoded.
 */
export default function SourcesPage() {
  const { t } = useTranslation();
  const sources = allSources();

  return (
    <section>
      <h1 className="fr-h1">{t("sources.title")}</h1>
      <p className="fr-text--lead">{t("sources.intro")}</p>
      <p className="fr-text--sm">{t("sources.updatedAt", { date: registryUpdatedAt })}</p>

      <div className="fr-table">
        <table>
          <caption>{t("sources.tableCaption")}</caption>
          <thead>
            <tr>
              <th scope="col">{t("sources.col.publisher")}</th>
              <th scope="col">{t("sources.col.licence")}</th>
              <th scope="col">{t("sources.col.cadence")}</th>
              <th scope="col">{t("sources.col.description")}</th>
            </tr>
          </thead>
          <tbody>
            {sources.map((source) => (
              <tr key={source.id} id={`source-${source.id}`}>
                <th scope="row">{source.publisher}</th>
                <td>{source.licence}</td>
                <td>{source.cadence}</td>
                <td>{source.description}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="fr-text--sm">{t("sources.attribution")}</p>
    </section>
  );
}
