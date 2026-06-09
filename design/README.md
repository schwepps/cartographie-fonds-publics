# Design reference — Cartographie des Fonds Publics

This folder is the **canonical design export** delivered for the project's UI. It is a
**reference, not built code** — nothing here is imported by the application bundle.

The live, built copies of the design system live in the web package:

- Styles & fonts → `packages/web/src/styles/` (`tokens.css`, `dsfr.css`, `app.css`, `fonts/`).
  These are the **source of truth for the running app** — edit them there, not here.
- Base component library → `packages/web/src/lib/ui/` (typed TSX ports of `js/icons.jsx`,
  `js/components.jsx`) and the shell → `packages/web/src/app/shell/` (port of `js/shell.jsx`).

## What's here

| Path | What it is | Status |
| --- | --- | --- |
| `css/{tokens,dsfr,app}.css` | Design tokens, DSFR-faithful base/components, app chrome | **Ported** → `packages/web/src/styles/` |
| `fonts/Marianne-*.woff2` | Marianne fonts | **Ported** → `packages/web/src/styles/fonts/` |
| `js/{icons,components,shell}.jsx` | Icon set, base components, app shell | **Ported** to typed TSX (FSC-49) |
| `js/screen-*.jsx`, `js/graph.jsx`, `js/sankey.jsx` | Per-screen reference implementations (home, graph, fiche, recherche, données, flux/sankey) | **Reference** for the per-screen redesign + Flux tickets |
| `js/{data,util}.js` | Illustrative fixtures + helpers (`util.js` ported to `src/lib/`; the app reads real Supabase data, not `data.js`) | Reference |
| `screenshots/*.png` | Visual acceptance reference | Reference |
| `Cartographie des Fonds Publics.html` | Standalone prototype (open in a browser to preview all screens) | Reference |

## Why keep it

The shell + base components are ported in FSC-49, but the **per-screen redesigns and the
Flux/Sankey screen** are separate follow-up tickets that build directly on `js/screen-*.jsx` and
`screenshots/`. Keeping the full export versioned here gives those tickets — and any contributor —
a durable spec without re-obtaining the original archive.
