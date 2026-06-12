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
- The committed crosswalk holds the **full ~431-operator population** (FSC-56): the 285 `auto` rows
  are a live-spike snapshot (`make spike-resolve-live` → `make resolve-seed`, regenerable only with
  network), plus the curated `reviewed` rows and the `pending` backlog. A handful of clean-name
  `reviewed` rows (CNRS, BnF, France Travail) alias the live acronym-prefixed names so the offline
  seed (`supabase/seed.sql`) and the sample fixtures stay deterministic in CI.

## Assisted curation (`make curate`, FSC-56)

`make curate` (CLI `curate-operators`) re-queries recherche-entreprises for each `pending` operator
and promotes it to `reviewed` **only** on a *single, unambiguous, public-sector* match — by exact
name, the candidate's own `sigle` (acronym), or full name-containment. Anything ambiguous (several
public matches) or unmatched stays `pending`, never guessed (golden rule #5). Every promoted row's
`notes` carry the API basis (legal name + nature juridique + signal), `source: api-curated`. It is
**dry-run by default** (reports what would move); pass `--apply` to write. Re-running is idempotent
and never downgrades a human `reviewed` row.

The residual `pending` rows are the documented human-review queue; promote them by hand (the review
action above) toward the ≥90% coverage target. `make coverage` reports the current operator→SIREN
coverage over the committed crosswalk (`out/coverage_report.json`).

## How it runs

```bash
make resolve   # resolve the offline operator sample against this crosswalk; writes
               # out/resolution_report.json and exits nonzero if the resolution rate < 50%.
```

The report (`out/`) is generated output and **gitignored**; only this crosswalk + README are
committed.

## `ministeres.yaml` — the tutelle-ministry reference (FSC-25)

`operateurs.yaml` resolves an *operator* name to its SIREN. It does **not** know a ministry's SIREN,
yet a `tutelle` edge (`ministry → operator`) needs one on each side. `ministeres.yaml` is the
curated, hand-maintained map that fills that gap.

- **Schema:** the same `CrosswalkEntry` rows, but here a row's `tutelle` field holds the **ministry's
  own code** (the value an operator references in the Jaune, e.g. `MESR`), `denomination` is the
  ministry's canonical name (the entity node), and `siren` its own SIREN. All rows are `reviewed`.
- **Resolution:** the operator transform resolves an operator's tutelle by **code** (case-insensitive)
  with a normalized-name fallback (`ingestion.transforms.operateurs_etat.MinistryIndex`), so it works
  whether the live Jaune emits `MESR` or the full ministry label.
- **Governance:** hand-curated, **never generated** (unlike `operateurs.yaml`'s `auto`/`pending`
  rows). Loading fails loud on a missing or duplicate tutelle code, or a malformed SIREN
  (`ingestion.crosswalk_io.load_ministries`). SIRENs are verified against
  annuaire-/recherche-entreprises (central-State administrations, *nature juridique* 7113); record
  `reviewed_by`/`reviewed_at`. The committed file is a partial seed covering the offline sample's
  codes — add ministries by review as the full operator crosswalk lands.

```bash
make operators   # transform the offline operator sample into entities + tutelle edges; writes
                 # out/operators_report.json and exits nonzero if the resolution rate < 50%.
```

## `missions.yaml` — the LOLF-mission → tutelle-ministry reference (FSC-56)

The live Jaune records an operator's supervision as a LOLF **mission** (e.g. *« Recherche et
enseignement supérieur »*), not a ministry code. `missions.yaml` maps each mission to the code of its
**lead ministry** in `ministeres.yaml`, so `MinistryIndex` can anchor a `ministry → operator` tutelle
edge for the full population (the offline sample uses codes directly and is unaffected).

- **Schema:** `missions:` is a list of `{mission, tutelle}` rows; `tutelle` is a code that **must**
  exist in `ministeres.yaml` (`MinistryIndex` fails loud otherwise — never mis-resolve a tutelle).
- **Governance:** hand-curated, never generated. It is a documented *lead-ministry* heuristic: a few
  missions are interministerial (e.g. *« Cohésion des territoires »*, *« Direction de l'action du
  Gouvernement »*) and are mapped to the single most defensible responsible ministry, with a note.
- **Resolution order:** `MinistryIndex.resolve` tries the ministry **code**, then the ministry
  **name**, then the **mission** on the first line of the Jaune's `"Mission\nNNN – Programme"` cell.
