# 6. react-dsfr as the web DSFR layer

- Status: accepted
- Date: 2026-06-09
- Refines the "UI system" choice in [ADR-0005](0005-supabase-vercel-baas.md) /
  ARCHITECTURE.md. `@gouvfr/dsfr` remains the design system; this records *how* we consume
  it from React.

## Context
ARCHITECTURE.md lists the UI system as `@gouvfr/dsfr` ("plain CSS"). Using the plain CSS
package directly means hand-writing DSFR markup (header/footer/nav/modals) and wiring its
JavaScript runtime by hand — error-prone and verbose for a React SPA, especially as the
header, navigation, and interactive components (menus, modals) accrete across feature lanes.

## Decision
- The web layer uses **`@codegouvfr/react-dsfr`**, the officially-maintained typed React
  binding, layered **on top of `@gouvfr/dsfr`** (which it depends on). It provides typed
  `Header`/`Footer`/etc. components and manages the DSFR JS runtime and color scheme.
- Vite SPA integration: `startReactDsfr(...)` boots the runtime in `src/main.tsx`, with
  react-router's `Link` registered so DSFR components navigate client-side. DSFR static
  assets are copied to `packages/web/public/dsfr/` by `copy-dsfr-to-public` (run on
  `postinstall`, `dev`, and `build`); that folder is gitignored.

## Consequences
- Less bespoke DSFR markup; accessibility and gov-compliance handled by the binding.
- One extra dependency and a build step (`copy-dsfr-to-public`). Assets are served
  same-origin under `/dsfr/`, consistent with the current CSP (`'self'`).
- `@gouvfr/dsfr` is still the source of truth for design tokens/CSS; we can drop to plain
  DSFR classes (e.g. `fr-container`, `fr-h1`) anywhere without the binding.
