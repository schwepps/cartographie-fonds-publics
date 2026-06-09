import type { RouteObject } from "react-router-dom";
import type { FeatureRoute } from "./feature-route";
import homeRoute from "../features/home/route";
import searchRoute from "../features/search/route";
import sourcesRoute from "../features/sources/route";
import entityRoute from "../features/entity/route";

/**
 * Feature registry — THE one shared file edited per feature.
 *
 * To register a feature: import its route descriptor and add it to the array
 * below. `App.tsx` stays frozen; everything else lives under `src/features/<name>/`.
 */
const registered: FeatureRoute[] = [homeRoute, searchRoute, sourcesRoute, entityRoute];

/**
 * Fails loud on cross-lane collisions — two index routes, duplicate paths, or a
 * non-index route with an empty path. Runs at module load so a bad registration
 * breaks dev/build/test immediately and points at the convention, instead of a
 * cryptic react-router error. This is the guard that keeps parallel feature lanes safe.
 */
export function assertValidRegistry(routes: readonly FeatureRoute[]): void {
  const indexCount = routes.filter((route) => route.index).length;
  if (indexCount > 1) {
    throw new Error(
      `Feature registry: ${indexCount} routes set index: true — exactly one feature may claim the index ("/").`,
    );
  }
  const seen = new Set<string>();
  for (const route of routes) {
    if (route.path === "" && !route.index) {
      throw new Error(
        'Feature registry: a route has path "" without index: true. Use index: true for the home route.',
      );
    }
    const key = route.index ? "/" : `/${route.path}`;
    if (seen.has(key)) {
      throw new Error(
        `Feature registry: duplicate route "${key}" — each feature must register a unique path.`,
      );
    }
    seen.add(key);
  }
}

assertValidRegistry(registered);

/** Descriptors sorted by `order` — drives both the router and the nav (DRY). */
export const featureRoutes: FeatureRoute[] = [...registered].sort(
  (a, b) => (a.order ?? 100) - (b.order ?? 100),
);

/** react-router children for the Layout root route. */
export const featureRouteObjects: RouteObject[] = featureRoutes.map((route) =>
  route.index
    ? { index: true, Component: route.Component }
    : { path: route.path, Component: route.Component },
);

/** Derives header nav links from descriptors; routes without `nav` are omitted. */
export function toNavItems(routes: readonly FeatureRoute[]): { to: string; label: string }[] {
  return routes.flatMap((route) =>
    route.nav ? [{ to: route.index ? "/" : `/${route.path}`, label: route.nav.label }] : [],
  );
}

/** Header navigation links, derived from the same descriptors. */
export const navItems = toNavItems(featureRoutes);
