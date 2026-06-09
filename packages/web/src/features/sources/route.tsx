import { lazy } from "react";
import type { FeatureRoute } from "../../app/feature-route";

const route: FeatureRoute = {
  path: "sources",
  Component: lazy(() => import("./SourcesPage")),
  nav: { label: "Données & licences" },
  order: 30,
};

export default route;
