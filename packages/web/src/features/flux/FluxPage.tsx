import { useTranslation } from "react-i18next";
import { Callout } from "../../lib/ui";

/**
 * Placeholder for the funding-flow (Sankey) screen so the nav entry "Flux de financement" resolves
 * instead of 404-ing. The full visualisation lands in its own ticket, built on
 * `design/js/sankey.jsx`.
 */
export default function FluxPage() {
  const { t } = useTranslation();
  return (
    <section>
      <h1 className="fr-h1">{t("flux.title")}</h1>
      <p className="fr-lead">{t("flux.intro")}</p>
      <Callout tone="info">{t("flux.comingSoon")}</Callout>
    </section>
  );
}
