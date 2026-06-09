# Feature folders

Every web feature is a **self-contained folder** under `src/features/<name>/`. The app
shell (`src/App.tsx`, `src/app/Layout.tsx`) is **frozen** — you never edit it to add a
feature. This is what lets feature lanes (entity sheet, graph explorer, provenance UI,
Sankey, overview…) progress in parallel without colliding.

## Anatomy

```
src/features/<name>/
├── <Name>Page.tsx   # the page component — default export
└── route.tsx        # the FeatureRoute descriptor — default export
```

A feature may add anything else it needs (components, hooks, queries) inside its own
folder. It should only import from `src/lib/*`, `src/app/feature-route`, and its own files.

## Add a feature in two steps

1. **Create the folder** with a page and a `route.tsx` descriptor:

   ```tsx
   // src/features/operators/OperatorsPage.tsx
   // The page MUST be a default export so React.lazy can load it.
   export default function OperatorsPage() {
     return <h1 className="fr-h1">Opérateurs</h1>;
   }
   ```

   ```tsx
   // src/features/operators/route.tsx
   import { lazy } from "react";
   import type { FeatureRoute } from "../../app/feature-route";

   const route: FeatureRoute = {
     path: "operators", // "" + index: true for the home route
     Component: lazy(() => import("./OperatorsPage")), // lazy → code-split, keeps the bundle small
     nav: { label: "Opérateurs" }, // omit `nav` for a route with no header link
     order: 20, // nav ordering (lower = first); space by 10s
   };

   export default route;
   ```

2. **Register it** with a single line in `src/app/routes.tsx` — import the descriptor and add
   it to the `registered` array. That is the only shared file you touch.

The registry validates itself at load time (`assertValidRegistry`): exactly one `index` route,
unique `path`s, and `path: ""` only with `index: true`. A collision fails the build/test loudly
rather than producing a cryptic router error — so independent lanes stay safe. Pick distinct
`order` values (home `0`, search `10`, then `20`, `30`…); equal values fall back to registration
order.

The descriptor is the single source of truth: it drives both the router and the header
navigation. Lazy-load the page component so heavy pages (Sigma graph, D3 Sankey) stay
code-split behind the shell's shared `<Suspense>`.

## Accessibility & i18n (baseline, FSC-30)

- **i18n**: strings go through `useTranslation()` (keys in `src/locales/{fr,en}.json`); `fr` is the
  default + fallback. Don't hardcode user-facing copy in components.
- **Non-visual fallback**: every **graphical** view (Sigma graph, D3 Sankey…) MUST also render
  `DataTableFallback` (`src/lib/a11y/DataTableFallback.tsx`) with equivalent data, so the information
  is reachable without sight. The entity sheet shows the pattern.
- **Provenance**: surface a figure's source with `ProvenanceBadge` (`src/lib/provenance/`); values
  are read from the registry, never hardcoded.
- Automated a11y checks run in `pnpm test` via `vitest-axe` — add a `toHaveNoViolations()` assertion
  for new pages.

## Global search

The header search bar lives in the shared `Layout` and navigates to `/search?q=…`. The
`search` feature owns rendering the results — see `src/features/search/`.
