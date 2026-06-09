# Entity-resolution crosswalk — review process

`operateurs.yaml` is the **reviewed, versioned crosswalk** that maps an entity name to its SIREN
for entities that carry no SIREN of their own. It is the hard-case half of **golden rule #5**
("SIREN is the canonical join key… unresolved links go to the reviewed crosswalk — never guess,
never silently drop"). The resolver (`core.resolution.resolve_entities`) consults it for every
entity that lacks a SIREN; anything it cannot resolve is surfaced in the unresolved-links report,
never dropped.

## What this is — and is not

- **It is** an exact name→SIREN map. The lookup key is `normalize_name(denomination)` (accent-/
  case-folded, articles + bare legal forms stripped). A crosswalk row and the entity it resolves
  agree on that key by construction.
- **It is not** a fuzzy matcher. Only two kinds of row ever yield a SIREN: `auto` (a reproducible
  *exact* normalized-name match, machine-seeded) and `reviewed` (human-confirmed). Everything else
  yields nothing and stays in the backlog. We never guess.

## Row schema

| Field | Meaning |
| -- | -- |
| `denomination` | The entity name as it appears upstream (the Jaune). **Source of truth** for the key. |
| `status` | `auto` \| `reviewed` \| `pending` \| `category` (see lifecycle below). |
| `siren` | 9-digit SIREN. **Required** for `auto`/`reviewed`; **must be absent** for `pending`/`category`. |
| `tutelle` | Supervising-ministry code (a reviewer disambiguator). |
| `candidate_sirens` | Candidate SIRENs for an ambiguous row — reviewer hints, never auto-accepted. |
| `top_match_ratio` | difflib similarity hint for the backlog (descriptive only). |
| `source` | Provenance: `spike-auto`, `spike-backlog`, `manual`, … |
| `reviewed_by` / `reviewed_at` | Who confirmed a `reviewed` row, and when (ISO date). |
| `notes` | Free-text justification / cross-reference. |

Invariants are enforced **loud** at load time (`ingestion.crosswalk_io.load_crosswalk`): a malformed
SIREN, an accepted row missing its SIREN, a backlog row carrying one, or two rows whose names share
a normalized key but map to different SIRENs all raise — the run fails rather than silently
mis-resolving.

## Status lifecycle

```
pending ──(reviewer confirms a SIREN)──▶ reviewed     ← yields a SIREN
auto     ──(reviewer overrides)────────▶ reviewed     ← yields a SIREN
pending ──(it's a category label)──────▶ category     ← yields nothing, by design
```

- **`auto`** — machine-seeded from an exact normalized-name match against SIRENE
  (recherche-entreprises). Reproducible from the seed run; auditable via `top_match_ratio`/`source`.
  Treated as accepted because the match rule is exact, not heuristic.
- **`pending`** — needs human review. No SIREN. These rows **are** the curation backlog.
- **`reviewed`** — a human confirmed the SIREN (e.g. on annuaire-entreprises.data.gouv.fr / SIRENE).
- **`category`** — a category label (e.g. *"Universités et assimilés"*) with no own SIREN. Kept so
  it is counted and explained, not mistaken for an unresolved operator.

### Turning a `pending` row into `reviewed` (the review action)

A reviewer (role: the data maintainer / a delegated contributor — not a personal inbox) edits the
row **by hand**:

1. Confirm the entity's SIREN against an authoritative source (SIRENE / annuaire-entreprises),
   using `candidate_sirens` + `tutelle` as starting hints.
2. Set `siren`, change `status` to `reviewed`, and record `reviewed_by` + `reviewed_at` (ISO date)
   and a short `notes` justification.
3. Commit as a Conventional Commit (golden rule #9), one logical change per commit.

If a `category` row is the right call instead, set `status: category` (and leave `siren` empty).

## Versioning & regeneration

- The file is **git-tracked** and carries `schema_version`. One logical change per commit.
- `make resolve-seed` regenerates `auto`/`pending` rows from the resolver-spike CSV and is
  **merge-aware**: it **preserves** existing `reviewed` and `category` rows (your curation is never
  clobbered). Do not hand-edit `auto`/`pending` rows — re-seed instead; only `reviewed`/`category`
  rows are hand-maintained.
- This repo seeds from the **offline sample** (5 operators) so CI stays deterministic. The full
  ~431-operator crosswalk is produced by a maintainer running `make spike-resolve-live` (≈430
  network calls) then `make resolve-seed`; the resulting 285 `auto` + 146 `pending` rows are the
  one-time governance backlog (see `docs/phase0_5-operator-resolution-results.md`).

## How it runs

```bash
make resolve   # resolve the offline operator sample against this crosswalk; writes
               # out/resolution_report.json and exits nonzero if the resolution rate < 50%.
```

The report (`out/`) is generated output and **gitignored**; only this crosswalk + README are
committed.
