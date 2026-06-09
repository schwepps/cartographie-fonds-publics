import { lazy } from "react";
import type { FeatureRoute } from "../../app/feature-route";

const route: FeatureRoute = {
  path: "flux",
  Component: lazy(() => import("./FluxPage")),
  nav: { label: "Flux de financement", icon: "Flow" },
  order: 30,
};

export default route;
