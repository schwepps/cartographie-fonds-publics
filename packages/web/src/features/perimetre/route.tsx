import { lazy } from "react";
import type { FeatureRoute } from "../../app/feature-route";

/**
 * Whole-perimeter overview (FSC-44): a top-level summary of the four spheres (State, local, social,
 * delegated) with per-level headline figures, provenance and methodology notes. Sits right after the
 * home landing in the nav (order 5).
 */
const route: FeatureRoute = {
  path: "perimetre",
  Component: lazy(() => import("./PerimetrePage")),
  nav: { label: "Aperçu du périmètre", icon: "Layers" },
  order: 5,
};

export default route;
