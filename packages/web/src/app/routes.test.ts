import { describe, expect, it } from "vitest";
import appSource from "../App.tsx?raw";
import {
  assertValidRegistry,
  featureRouteObjects,
  featureRoutes,
  navItems,
  toNavItems,
} from "./routes";
import type { FeatureRoute } from "./feature-route";

const Stub = () => null;

describe("feature route registry", () => {
  it("registers the home (index) and search features", () => {
    const home = featureRoutes.find((route) => route.index);
    expect(home?.nav?.label).toBe("Accueil");
    expect(featureRoutes.some((route) => route.path === "search")).toBe(true);
  });

  it("derives ordered nav items from the descriptors (design nav order)", () => {
    expect(navItems.map((item) => item.label)).toEqual([
      "Accueil",
      "Aperçu du périmètre",
      "Graphe institutionnel",
      "Recherche",
      "Flux de financement",
      "Données & licences",
    ]);
    expect(navItems.map((item) => item.to)).toEqual([
      "/",
      "/perimetre",
      "/graph",
      "/search",
      "/flux",
      "/sources",
    ]);
  });

  it("carries an icon name on each nav item for the header glyphs", () => {
    expect(navItems.every((item) => typeof item.icon === "string")).toBe(true);
  });

  // Guards the header's "Rechercher" tool link → /search: if the search lane renames its slug,
  // this fails loudly instead of silently 404-ing.
  it("always registers the `search` route the header tool link depends on", () => {
    expect(featureRouteObjects.some((r) => "path" in r && r.path === "search")).toBe(true);
  });
});

describe("toNavItems", () => {
  it("omits routes that have no nav metadata", () => {
    const routes: FeatureRoute[] = [
      { path: "visible", Component: Stub, nav: { label: "Visible" } },
      { path: "hidden", Component: Stub },
    ];
    expect(toNavItems(routes).map((i) => i.label)).toEqual(["Visible"]);
  });
});

describe("assertValidRegistry", () => {
  it("accepts a valid registry", () => {
    expect(() => assertValidRegistry(featureRoutes)).not.toThrow();
  });

  it("rejects two index routes (parallel-lane collision)", () => {
    expect(() =>
      assertValidRegistry([
        { path: "", index: true, Component: Stub },
        { path: "", index: true, Component: Stub },
      ]),
    ).toThrow(/index/i);
  });

  it("rejects duplicate paths", () => {
    expect(() =>
      assertValidRegistry([
        { path: "dup", Component: Stub },
        { path: "dup", Component: Stub },
      ]),
    ).toThrow(/duplicate/i);
  });

  it("rejects an empty path without index", () => {
    expect(() => assertValidRegistry([{ path: "", Component: Stub }])).toThrow(/index/i);
  });
});

describe("app shell is frozen", () => {
  // The ticket's invariant: features register in routes.tsx, never by editing
  // App.tsx. If a feature import leaks into App.tsx, this fails.
  it("App.tsx imports nothing from src/features", () => {
    expect(appSource).not.toMatch(/from\s+["'][^"']*\/features\//);
  });
});
