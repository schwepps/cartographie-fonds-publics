import React from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import "./lib/i18n"; // initialise i18next (fr default) before first render
// Project design system (self-contained, ported from the delivered `design/` export):
// tokens → DSFR-faithful base/components → app chrome. Order matters.
import "./styles/tokens.css";
import "./styles/dsfr.css";
import "./styles/app.css";

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
