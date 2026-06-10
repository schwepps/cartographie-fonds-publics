import { describe, expect, it } from "vitest";
import { euroCompact, euroFull } from "./format";

// fr-FR uses a narrow no-break space (U+202F) or no-break space (U+00A0) as the thousands
// separator. `\s` matches both, so collapse all whitespace to a plain space — assertions then
// stay stable across ICU versions.
const norm = (s: string) => s.replace(/\s/g, " ");

describe("euroCompact", () => {
  it("formats billions as Md€ with one decimal", () => {
    expect(norm(euroCompact(31_200_000_000))).toBe("31,2 Md€");
  });

  it("formats millions as M€ (rounded ≥ 10 M€, one decimal below)", () => {
    expect(norm(euroCompact(254_000_000))).toBe("254 M€");
    expect(norm(euroCompact(5_400_000))).toBe("5,4 M€");
  });

  it("formats thousands as whole euros with separators", () => {
    expect(norm(euroCompact(84_925))).toBe("84 925 €");
  });

  it("formats small amounts with up to two decimals", () => {
    expect(norm(euroCompact(12.5))).toBe("12,5 €");
  });

  it("treats 0 as a real value, not absent", () => {
    expect(norm(euroCompact(0))).toBe("0 €");
  });

  it("renders null/undefined as an em dash", () => {
    expect(euroCompact(null)).toBe("—");
    expect(euroCompact(undefined)).toBe("—");
  });
});

describe("euroFull", () => {
  it("renders the full amount with separators", () => {
    expect(norm(euroFull(84_925))).toBe("84 925 €");
  });

  it("renders null as an em dash and 0 as a value", () => {
    expect(euroFull(null)).toBe("—");
    expect(norm(euroFull(0))).toBe("0 €");
  });
});
