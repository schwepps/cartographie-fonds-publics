import { Suspense } from "react";
import { Footer } from "@codegouvfr/react-dsfr/Footer";
import { Header } from "@codegouvfr/react-dsfr/Header";
import { SkipLinks } from "@codegouvfr/react-dsfr/SkipLinks";
import { useTranslation } from "react-i18next";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { navItems } from "./routes";

const BRAND_TOP = (
  <>
    République
    <br />
    Française
  </>
);

const HOME_LINK_PROPS = {
  to: "/",
  title: "Accueil — Cartographie des Fonds Publics",
} as const;

/**
 * App shell: DSFR header (with the global search entry point) + footer wrapping
 * a <Suspense><Outlet/></Suspense>. The single Suspense covers every lazy
 * feature page, so feature authors never write their own boundary.
 */
export function Layout() {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const { t } = useTranslation();

  return (
    <>
      <SkipLinks links={[{ anchor: "#content", label: t("shell.skipToContent") }]} />
      <Header
        brandTop={BRAND_TOP}
        homeLinkProps={HOME_LINK_PROPS}
        serviceTitle="Cartographie des Fonds Publics"
        serviceTagline={t("shell.tagline")}
        navigation={navItems.map((item) => ({
          text: item.label,
          linkProps: { to: item.to },
          isActive: pathname === item.to,
        }))}
        onSearchButtonClick={(text) => navigate(`/search?q=${encodeURIComponent(text.trim())}`)}
      />
      <main role="main" id="content" className="fr-container fr-my-4w">
        <Suspense fallback={<p className="fr-text--lead">{t("shell.loading")}</p>}>
          <Outlet />
        </Suspense>
      </main>
      <Footer
        accessibility="non compliant"
        brandTop={BRAND_TOP}
        homeLinkProps={HOME_LINK_PROPS}
        contentDescription={t("shell.footer")}
      />
    </>
  );
}
