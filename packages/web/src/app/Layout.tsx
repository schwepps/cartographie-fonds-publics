import { Suspense } from "react";
import { Outlet } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Header } from "./shell/Header";
import { Footer } from "./shell/Footer";

/**
 * App shell: a sticky-footer column (`#app`) wrapping the Marianne header, the routed page, and the
 * footer. A skip link jumps to `#content`; the single `<Suspense>` covers every lazy feature page,
 * so feature authors never write their own boundary. The shell is the design's ported chrome
 * (`src/app/shell/`), styled by the project design layer in `src/styles/`.
 */
export function Layout() {
  const { t } = useTranslation();

  return (
    <div id="app">
      <a className="skip-link" href="#content">
        {t("shell.skipToContent")}
      </a>
      <Header />
      <main className="main" id="content" tabIndex={-1} role="main">
        <Suspense fallback={<p className="fr-lead">{t("shell.loading")}</p>}>
          <Outlet />
        </Suspense>
      </main>
      <Footer />
    </div>
  );
}
