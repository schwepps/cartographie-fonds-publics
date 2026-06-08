import { lazy } from "react";
import type { FeatureRoute } from "../../app/feature-route";

const route: FeatureRoute = {
  path: "",
  index: true,
  Component: lazy(() => import("./HomePage")),
  nav: { label: "Accueil" },
  order: 0,
};

export default route;
