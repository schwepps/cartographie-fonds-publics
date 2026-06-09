import { describe, expect, it } from "vitest";
import { LEVELS, UNRESOLVED_META, levelMeta } from "./levels";
import { SEQ, seqColor } from "./seq";

describe("LEVELS", () => {
  it("covers exactly the DB-constrained level values", () => {
    // Mirrors `level in ('state','local','social','delegated')` in 0001_init.sql.
    expect(Object.keys(LEVELS).sort()).toEqual(["delegated", "local", "social", "state"]);
  });

  it("uses the Okabe–Ito hues (distinct from Bleu France #000091)", () => {
    expect(LEVELS.state.color).toBe("#0072b2");
    expect(Object.values(LEVELS).map((l) => l.color)).not.toContain("#000091");
  });

  it("gives each level a distinct non-colour shape cue", () => {
    const shapes = Object.values(LEVELS).map((l) => l.shape);
    expect(new Set(shapes).size).toBe(shapes.length);
  });
});

describe("levelMeta", () => {
  it("returns the matching meta for a known level", () => {
    expect(levelMeta("delegated").label).toBe("Délégué");
    expect(levelMeta("state")).toBe(LEVELS.state);
  });

  it("falls back to the unresolved meta for unknown / null / undefined", () => {
    expect(levelMeta("unknown")).toBe(UNRESOLVED_META);
    expect(levelMeta(null)).toBe(UNRESOLVED_META);
    expect(levelMeta(undefined)).toBe(UNRESOLVED_META);
  });
});

describe("seqColor", () => {
  it("maps the endpoints to the ramp extremes", () => {
    expect(seqColor(0)).toBe(SEQ[0]);
    expect(seqColor(1)).toBe(SEQ[SEQ.length - 1]);
  });

  it("clamps out-of-range input", () => {
    expect(seqColor(-5)).toBe(SEQ[0]);
    expect(seqColor(99)).toBe(SEQ[SEQ.length - 1]);
  });

  it("returns an interior swatch for a mid value", () => {
    expect(SEQ).toContain(seqColor(0.5));
  });
});
