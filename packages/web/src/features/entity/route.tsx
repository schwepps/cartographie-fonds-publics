import { lazy } from "react";
import type { FeatureRoute } from "../../app/feature-route";

const route: FeatureRoute = {
  // Detail route reached by SIREN (e.g. from search); no header nav entry.
  path: "entity/:siren",
  Component: lazy(() => import("./EntityPage")),
  order: 50,
};

export default route;
