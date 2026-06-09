import { describe, expect, it } from "vitest";
import { allSources, getSource, licenceOf, licenseDefault, registryUpdatedAt } from "./sources";

describe("sources registry accessors", () => {
  it("exposes the registry-level default licence and updated date", () => {
    expect(licenseDefault).toMatch(/Licence Ouverte/i);
    expect(registryUpdatedAt).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });

  it("loads sources from the registry virtual module", () => {
    const sources = allSources();
    expect(sources.length).toBeGreaterThan(0);
    const ids = sources.map((s) => s.id);
    expect(ids).toContain("budget_plf_lfi");
    // Every source carries an attributable publisher and a resolved licence.
    for (const s of sources) {
      expect(s.publisher).toBeTruthy();
      expect(s.licence).toBeTruthy();
    }
  });

  it("resolves a source by its provenance id", () => {
    const source = getSource("budget_plf_lfi");
    expect(source?.publisher).toMatch(/Direction du budget/i);
    expect(source?.licence).toBeTruthy();
  });

  it("falls back to the registry default licence for an unknown id", () => {
    expect(getSource("does-not-exist")).toBeUndefined();
    expect(licenceOf("does-not-exist")).toBe(licenseDefault);
  });
});
