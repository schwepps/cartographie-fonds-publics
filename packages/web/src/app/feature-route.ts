import type { ComponentType, LazyExoticComponent } from "react";

/**
 * The contract every feature folder implements to register itself with the app
 * shell. A feature exports a default `FeatureRoute` from `src/features/<name>/route.tsx`,
 * then is listed once in `src/app/routes.tsx`. `App.tsx` never changes.
 *
 * This descriptor is the single source of truth: it drives both the router and
 * the header navigation.
 */
export interface FeatureRoute {
  /** URL path relative to the app root; "" for the index route, else a slug like "search". */
  path: string;
  /** Marks this as the index route (`path` is ignored when true). */
  index?: boolean;
  /** Page component rendered into the Layout outlet. Prefer `React.lazy` for code-splitting. */
  Component: ComponentType | LazyExoticComponent<ComponentType>;
  /** When present, the feature appears in the header navigation. Omit for a route with no nav link. */
  nav?: { label: string };
  /** Nav ordering; lower sorts first. Default 100. */
  order?: number;
}
