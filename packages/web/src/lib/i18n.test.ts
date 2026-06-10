import { afterEach, describe, expect, it } from "vitest";
import i18n, { FALLBACK_LANGUAGE } from "./i18n";

afterEach(async () => {
  await i18n.changeLanguage(FALLBACK_LANGUAGE);
});

describe("i18n", () => {
  it("defaults to French and resolves a known key", () => {
    expect(i18n.resolvedLanguage).toBe("fr");
    expect(i18n.t("shell.tagline")).toBe("Comprendre l'usage des fonds publics");
  });

  it("keeps <html lang> in sync when the language changes", async () => {
    await i18n.changeLanguage("en");
    expect(document.documentElement.lang).toBe("en");
    expect(i18n.t("shell.tagline")).toBe("Understand how public money is used");
  });
});
