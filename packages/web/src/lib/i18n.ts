import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import en from "../locales/en.json";
import fr from "../locales/fr.json";

/**
 * App i18n. French is the default and fallback; `en` ships as a structural stub so
 * the app is ready for more languages without retrofitting. Resources are bundled
 * inline (no async backend), so `t()` is usable synchronously after this import.
 *
 * Importing this module for its side effect (in `main.tsx` and the test setup) is
 * enough — react-i18next uses this default instance, so no Provider is required.
 */
export const FALLBACK_LANGUAGE = "fr";
export const SUPPORTED_LANGUAGES = ["fr", "en"] as const;

void i18n.use(initReactI18next).init({
  resources: {
    fr: { translation: fr },
    en: { translation: en },
  },
  lng: FALLBACK_LANGUAGE,
  fallbackLng: FALLBACK_LANGUAGE,
  supportedLngs: SUPPORTED_LANGUAGES,
  interpolation: { escapeValue: false }, // React already escapes
});

/** Keep <html lang> in sync for RGAA / assistive tech as the language changes. */
function syncDocumentLang(lng: string): void {
  if (typeof document !== "undefined") {
    document.documentElement.lang = lng;
  }
}

syncDocumentLang(i18n.resolvedLanguage ?? FALLBACK_LANGUAGE);
i18n.on("languageChanged", syncDocumentLang);

// `i18n` is the i18next singleton and survives HMR re-evaluation of this module, so
// drop the listener this evaluation registered when the module is replaced — otherwise
// dev HMR accumulates duplicate <html lang> handlers. No-op in prod/tests (no `hot`).
if (import.meta.hot) {
  import.meta.hot.dispose(() => {
    i18n.off("languageChanged", syncDocumentLang);
  });
}

export default i18n;
