import { lazy } from "react";
import type { FeatureRoute } from "../../app/feature-route";

const route: FeatureRoute = {
  path: "sources",
  Component: lazy(() => import("./SourcesPage")),
  nav: { label: "Données & licences", icon: "Scale" },
  order: 40,
};

export default route;
