import { describe, expect, it } from "vitest";
import {
  UNIVERSE_LOLF,
  UNIVERSE_M57,
  UNIVERSE_SOCIAL,
  mixesPerimeters,
  universeForLevel,
} from "./perimeter";

describe("perimeter (anti-double-counting mirror of core.methodology)", () => {
  it("maps a level to its budget universe; delegated/unknown have none", () => {
    expect(universeForLevel("state")).toBe(UNIVERSE_LOLF);
    expect(universeForLevel("local")).toBe(UNIVERSE_M57);
    expect(universeForLevel("social")).toBe(UNIVERSE_SOCIAL);
    expect(universeForLevel("delegated")).toBeNull();
    expect(universeForLevel(null)).toBeNull();
    expect(universeForLevel("bogus")).toBeNull();
  });

  it("flags a set of levels as mixed only when it spans >1 universe", () => {
    expect(mixesPerimeters(["state", "state"])).toBe(false);
    expect(mixesPerimeters(["state", "delegated"])).toBe(false); // delegated adds no universe
    expect(mixesPerimeters(["state", "local"])).toBe(true);
    expect(mixesPerimeters(["state", "local", "delegated"])).toBe(true);
    expect(mixesPerimeters([null, "local"])).toBe(false);
  });
});
