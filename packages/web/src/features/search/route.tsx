import { lazy } from "react";
import type { FeatureRoute } from "../../app/feature-route";

const route: FeatureRoute = {
  path: "search",
  Component: lazy(() => import("./SearchPage")),
  nav: { label: "Recherche", icon: "Search" },
  order: 20,
};

export default route;
