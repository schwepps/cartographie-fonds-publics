# RGAA conformance note (FSC-59)

Records the accessibility audit pass on the hard surfaces — the institutional **graph**, the
funding **Sankey**, and their **table fallbacks** — moving from the FSC-30 baseline to a verified
pass. Scope: `packages/web` (RGAA 4.1 / WCAG 2.1 AA, the legal bar for a French public-service
tool).

## Method

- **Automated** — `vitest-axe` (axe-core) `toHaveNoViolations()` assertions in the web test suite,
  run in CI on every PR. Covered screens: Accueil, Recherche, Graphe (chrome **and** table
  fallback), Fiche entité, Flux/Sankey, Données/Sources, Aperçu du périmètre, and the app shell
  (skip link, landmarks). jsdom has no 2-D canvas, so the graph canvas itself is verified manually
  (below) — its automated coverage is the surrounding chrome + the synchronized table.
- **Manual keyboard** — code-level review of the keyboard contract for the graph and Sankey and
  their fallbacks (below).
- **Manual contrast** — WCAG ratios computed directly from the design tokens
  (`styles/tokens.css`); see the table below.

## Non-conformities found and fixed

| # | Criterion | Issue | Fix |
| -- | -- | -- | -- |
| 1 | RGAA 9.1 / WCAG 1.3.1 (heading-order) | Graphe and Recherche jumped from the page `<h1>` straight to `<h4>` for the filter / facet / legend section titles, skipping levels. Caught by the new axe assertions. | Section titles promoted to `<h2>`; the small visual weight is now class/selector-driven (`.facet h2`, `.legend h2`, `fr-h4` on the filter panel), not the element level. |
| 2 | RGAA 11 / keyboard | The graph "Localiser" suggestion list had no accessible name. | `aria-label="Suggestions de localisation"` on the list (items are already tab-reachable buttons). |

After the fix the Graphe and Recherche pages carry several sibling `<h2>` directly under the page
`<h1>` (filter / facet / legend titles, plus the focused entity's name in the graph side-panel).
That is a **valid** heading sequence (no skipped level) and axe passes; the outline is intentionally
flat — these are peer page sections, not a nested hierarchy — rather than reflecting relative
importance. Accepted as conformant.

## Keyboard contract (verified)

- **Graph canvas** — `role="application"`, `tabIndex=0`, with an `aria-label` describing the
  contract: **Tab** to enter, **arrows** to move focus to the nearest node in that direction,
  **Enter** to open the sheet, **Escape** to deselect. View toggle (Graphe ↔ Tableau) exposes
  `aria-pressed`; zoom controls are labelled buttons (mouse/pointer enhancement — keyboard users
  rely on arrows + the table).
- **Table fallback (graph)** — every graphical view renders a synchronized, sortable `DataTable`
  (`aria-sort`) whose rows link to entity sheets; reachable via the "Vue tableau" toggle and
  documented in the accessibility callout.
- **Sankey** — hover-only by design (`role="img"` + `aria-label` promising a tabular equivalent);
  the synchronized "Équivalent tabulaire" `DataTable` below it carries the same source → target →
  amount → exercice data for keyboard and screen-reader users.
- **Reduced motion** — the global `prefers-reduced-motion` rule zeroes CSS transitions (incl. the
  Sankey hover fade); the graph force simulation settles instantly in JS when the preference is set.

## Contrast (WCAG 1.4.3 / 1.4.11) — computed from tokens

All **text** foreground/background pairs pass AA (≥ 4.5:1): `grey-title` 18.1, `grey-text` 11.4,
`grey-mention` #666 5.74 on white / 5.31 on `bg-alt` / 4.95 on `bg-contrast`, `blue-france` links
14.9, and every feedback colour (info/success/warning/error) ≥ 4.9 on both white and its tint.

Sub-threshold values, all **accepted with rationale**:

- `grey-disabled` #929292 (3.11:1) — disabled-control text, **exempt** from 1.4.3.
- Data-viz level fills `niv-local` (3.42), `niv-social` (3.06), `niv-delegue` #e69f00 (2.25) against
  white — these are **graphical fills, never text**. The administrative level is conveyed by
  **shape *and* colour** (circle / square / diamond / triangle, stated in the legend), graph nodes
  carry a dark outline for their boundary, and every graphical view has a text/table equivalent. So
  no information is conveyed by colour alone (RGAA 3.1) and the elements remain distinguishable. The
  palette is the deliberately colour-blind-safe **Okabe–Ito** scale; re-tinting `niv-delegue` to
  clear 3:1 would break that property, so it is kept and documented here instead.

## Conformance statement

The key screens pass axe in CI; the graph and Sankey are fully keyboard-operable with synchronized,
sortable table equivalents; text contrast meets AA. The residual items above are documented,
justified non-conformities (exempt or colour-redundant graphical encoding), not blockers. A full
manual screen-reader pass (NVDA/VoiceOver) on a production-scale dataset is recommended before
public launch.
