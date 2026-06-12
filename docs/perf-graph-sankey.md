# Performance — graph + Sankey on the full dataset (FSC-60)

Confirms the institutional graph and the funding Sankey stay responsive on the full local
perimeter (hundreds of nodes, thousands of contracts), records the budget, the before/after of
the fixes, and the evidence-based decision on the deferred Redis cache ([FSC-40]).

## What the UI actually loads

The web app does **not** call the `graph_neighbors` RPC. Both hot screens fetch the curated graph
once with plain PostgREST table selects and do all traversal/aggregation client-side:

| Hook | Query | Cap |
| -- | -- | -- |
| `useGraphData` | `entities` + `edges` + `budget_facts` (3 selects, `Promise.all`) | 5 000 / 20 000 rows |
| `useFluxData` | `entities` + `edges` | 5 000 / 20 000 rows |

So the bottleneck candidates are **client-side compute** (model build, visible-set, force
simulation, Sankey layout) and **canvas draw**, not the database.

## Budgets

| Phase | Budget | Basis |
| -- | -- | -- |
| First meaningful render | < 1.5 s | network-bound (2–3 PostgREST selects); model build is sub-ms (below) |
| Interaction compute (filter / focus / expand) | < 50 ms | well inside one 16 ms frame's worth of slack; keeps typing/filtering snappy |
| Sustained graph animation | ≥ 30 fps for the curated État-central perimeter | force sim is O(visible²); see "remaining cost" |

## Measurement — pure hot paths

`pnpm bench` (`src/features/graph/perf.bench.ts`) runs a deterministic synthetic graph an order of
magnitude past the demo seed (169 nodes / 102 edges), plus a stress tier. Mean per call:

| Path | full (1 622 nodes / 1 680 edges) | stress (3 244 / 3 360) |
| -- | -- | -- |
| `buildGraphModel` | 0.34 ms | 0.67 ms |
| `buildAdjacency` + `computeVisible` (all expanded) | 0.26 ms | 0.56 ms |
| `computeExpandable` (anchors-only expanded) | 0.008 ms | 0.016 ms |
| `buildFlowLinks` | 0.12 ms | 0.23 ms |
| `computeSankey` | 0.035 ms | 0.035 ms |

`computeVisible` is benched fully expanded (its worst case — the whole model becomes visible);
`computeExpandable` is benched with only the anchors expanded, so its adjacency scan actually runs
(with everything expanded it would early-exit and measure an empty loop). Every pure path is
**sub-millisecond even at ~3 000 nodes** — two orders of magnitude under the 50 ms interaction
budget. The Sankey aggregation + layout are trivial at this scale.

These benches cover the **pure precompute** paths. The per-frame `step()`/`draw()` cost is
characterized analytically below (it is a closure over the mutable simulation state, not a pure
function), not measured by a benchmark.

## The worst offender, fixed

The per-frame canvas work was the real risk. Before this pass, `draw()` (≈60 fps) recomputed the
"+" expand affordance per visible node with `hasHiddenNeighbours()`, an **O(edges) scan each** —
i.e. **O(visibleNodes × edges) per frame**. At the full tier that is ≈ 1 622 × 1 680 ≈ 2.7M
operations *per frame* (~160M/s at 60 fps) **on top of** the O(visible²) charge simulation, and
both `step()` and `draw()` re-`filter`ed the whole model array every frame.

Fixes (in `graph-model.ts` + `GraphCanvas.tsx`):

1. **Precompute the expandable set** — `computeExpandable` runs once per (visible, expanded) change
   (0.008 ms) over a prebuilt filtered adjacency; `draw()` now does an O(1) `Set.has()` per node.
   Eliminates the O(visibleNodes × edges) per-frame scan entirely.
2. **Precompute the visible node/edge subsets** (`st.visibleNodes` / `st.visibleEdges`) on change,
   so `step()` and `draw()` iterate small arrays instead of filtering the full model every frame.
3. **Bounded reduced-motion settle** — the fast-settle path ran a fixed `40 × step()` (40× O(n²))
   in a single frame, a multi-hundred-ms freeze at scale. It now steps until the layout is calm or a
   per-frame wall-clock budget (`SETTLE_MS = 12`) is spent: small graphs settle in one frame
   (instant, no perceptible motion), large ones converge over a frame or two, each bounded — never a
   freeze, and never the multi-second incremental drift a fixed low iteration count would have caused
   on a big graph (which would itself break the reduced-motion contract).
4. **Extracted `computeVisible`** out of the component into a pure, unit-tested, benchmarkable
   function (shared adjacency), removing the inline per-render duplication.

After the fixes, sustained per-frame cost is dominated by the O(visible²) charge integration alone
(the inherent naive-force cost), with no auxiliary full-model scans. For the curated État-central
perimeter (hundreds of visible nodes) this is **expected** to stay within the animation budget — at
e.g. 500 visible nodes the charge loop is ≈125k pair interactions/frame — but this is an analytic
estimate: the per-frame integration is not benchmarked and no production-scale dataset exists
locally yet, so it has not been confirmed by a frame-rate trace. A quadtree/Barnes–Hut charge
approximation is the documented next step **if** the visible perimeter grows into the thousands
(e.g. "Tout déplier" across the whole APU), and a `step()` benchmark should be added when that work
is scoped.

## Redis cache decision ([FSC-40]) — defer

**Verdict: not warranted yet.** [FSC-40] proposed Redis for *heavy RPCs*. There are none on the
read path: the UI issues plain PostgREST table selects (sub-200 ms), and `graph_neighbors` is
unused by the frontend. The measured bottleneck is client-side compute/render, which a server-side
cache cannot help. Revisit only if a server-side traversal RPC (e.g. `graph_neighbors` at
production scale, or a precomputed-aggregate RPC) is later put on the hot path — at which point the
measurement that flips the decision is that RPC's p95 latency exceeding the render budget.

[FSC-40]: https://linear.app/fscconsulting/issue/FSC-40
