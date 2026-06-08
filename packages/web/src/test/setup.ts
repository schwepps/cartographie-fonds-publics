import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";
import { startReactDsfr } from "@codegouvfr/react-dsfr/spa";
import "@testing-library/jest-dom/vitest";

// jsdom has no matchMedia; the DSFR runtime calls it on boot. Polyfill before
// startReactDsfr so it doesn't throw an unhandled rejection.
if (!window.matchMedia) {
  window.matchMedia = (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  });
}

// Initialise the DSFR runtime so react-dsfr components render in jsdom.
startReactDsfr({ defaultColorScheme: "light" });

// `globals: false` means vitest does not auto-clean the DOM between tests.
afterEach(() => {
  cleanup();
});
