import { afterEach, expect } from "vitest";
import { cleanup } from "@testing-library/react";
import * as axeMatchers from "vitest-axe/matchers";
import "@testing-library/jest-dom/vitest";
import "../lib/i18n"; // initialise i18next so t() returns real strings in tests

// Accessibility assertions: `expect(await axe(container)).toHaveNoViolations()`.
expect.extend(axeMatchers);

// jsdom has no matchMedia; polyfill it for components/tests that query media.
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

// `globals: false` means vitest does not auto-clean the DOM between tests.
afterEach(() => {
  cleanup();
});
