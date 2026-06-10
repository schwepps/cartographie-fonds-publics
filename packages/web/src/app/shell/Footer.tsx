import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { navItems } from "../routes";
import { MarianneBloc } from "./MarianneBloc";

const ETALAB_LICENCE_URL = "https://www.etalab.gouv.fr/licence-ouverte-open-licence/";

/**
 * App footer — Marianne bloc-marque, a description, the registry-driven primary links plus
 * methodology / licence / legal links, and the copyright mention. Ported from `design/`
 * (`shell.jsx`). Legal pages don't exist yet, so those links point at the sources page as a
 * placeholder until their tickets land.
 */
export function Footer() {
  const { t } = useTranslation();
  const year = new Date().getFullYear();

  return (
    <footer className="footer" role="contentinfo">
      <div className="fr-container">
        <div className="footer__body">
          <div>
            <MarianneBloc />
            <p className="footer__desc">{t("shell.footerDescription")}</p>
          </div>
          <nav className="footer__links" aria-label={t("shell.footerLinksLabel")}>
            {navItems.map((item) => (
              <Link key={item.to} to={item.to}>
                {item.label}
              </Link>
            ))}
            <Link to="/sources">{t("shell.methodology")}</Link>
            <a href={ETALAB_LICENCE_URL} target="_blank" rel="noopener noreferrer">
              {t("shell.openLicense")}
            </a>
            <Link to="/sources">{t("shell.sourceCode")}</Link>
          </nav>
        </div>
        <div className="footer__bottom">
          <Link to="/sources">{t("shell.legalNotice")}</Link>
          <Link to="/sources">{t("shell.personalData")}</Link>
          <Link to="/sources">{t("shell.cookies")}</Link>
          <Link to="/sources">{t("shell.accessibilityPartial")}</Link>
          <span className="fr-xs text-mention">{t("shell.copyright", { year })}</span>
        </div>
      </div>
    </footer>
  );
}
