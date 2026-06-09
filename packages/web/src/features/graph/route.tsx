import { lazy } from "react";
import type { FeatureRoute } from "../../app/feature-route";

const route: FeatureRoute = {
  path: "graph",
  // Sigma is heavy (WebGL) — lazy-load so it stays code-split behind the shell's <Suspense>.
  Component: lazy(() => import("./GraphPage")),
  nav: { label: "Graphe institutionnel" },
  order: 50,
};

export default route;
