import { lazy } from "react";
import type { FeatureRoute } from "../../app/feature-route";

const route: FeatureRoute = {
  path: "search",
  Component: lazy(() => import("./SearchPage")),
  nav: { label: "Recherche" },
  order: 10,
};

export default route;
