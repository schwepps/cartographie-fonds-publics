import React from "react";
import { createRoot } from "react-dom/client";
import { startReactDsfr } from "@codegouvfr/react-dsfr/spa";
import { Link } from "react-router-dom";
import { App } from "./App";

// Register react-router's Link so DSFR components (Header nav, Footer…) navigate
// client-side. `to` then becomes the canonical link prop across the app.
declare module "@codegouvfr/react-dsfr/spa" {
  interface RegisterLink {
    Link: typeof Link;
  }
}

// Boots the DSFR runtime (color scheme + assets injected from /dsfr/, populated
// by `copy-dsfr-to-public`). Must run before the first render.
startReactDsfr({ defaultColorScheme: "system", Link });

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
