import { afterEach, expect } from "vitest";
import { cleanup } from "@testing-library/react";
import { startReactDsfr } from "@codegouvfr/react-dsfr/spa";
import * as axeMatchers from "vitest-axe/matchers";
import "@testing-library/jest-dom/vitest";
import "../lib/i18n"; // initialise i18next so t() returns real strings in tests

// Accessibility assertions: `expect(await axe(container)).toHaveNoViolations()`.
expect.extend(axeMatchers);

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
