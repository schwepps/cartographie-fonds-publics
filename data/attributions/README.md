# Ministerial attributions (FSC-27)

Editorial, manual-first source of **legal mandates** attached to ministries — the "why" layer
(décrets d'attribution). One file, `ministres.yaml`, transformed by
`packages/ingestion/src/ingestion/transforms/legifrance_attributions.py` into `attributions` rows
(resolved to a SIREN via `data/crosswalk/ministeres.yaml`, never guessed — golden rule #5) and
surfaced on the entity fiche (« Attributions / mandat légal »).

Every entry is **real and verifiable** (golden rule #10): a published décret d'attribution with its
Légifrance/JORF URL. SIRENs are never written here — only the ministry `tutelle` code (or
`denomination`), resolved at build time.

## Why manual-first

This is the lowest-priority Phase-1 layer and not MVP-critical. Editorial curation of a handful of
key ministries is acceptable first; automation is a deliberate follow-up.

## Scaling path: text → entity (FSC-66, implemented — semi-automated)

The live discovery + deterministic linking is implemented. It is **semi-automated**: it produces
*candidates* for human review; it never auto-publishes. The published source of truth stays this
reviewed `ministres.yaml`.

1. **Discover + extract** via the PISTE/Légifrance API (registry source `legifrance_attributions`,
   `platform: rest`). PISTE uses OAuth2 client-credentials — set `PISTE_CLIENT_ID` /
   `PISTE_CLIENT_SECRET` (see `.env.example`; server/CI only, never the frontend). The `rest`
   connector (`connectors/rest.py`) mints the token, runs the LODA search for « décret
   d'attribution » (ids from the API, never frozen), and consults each text's full body.
2. **Link** text → entity deterministically (`transforms/legifrance_candidates.py`): a transparent
   token matcher maps a décret title to a ministry from the reviewed `ministeres.yaml`. A décret
   resolves only when **exactly one** ministry's distinctive tokens are all present (precision over
   recall). Ambiguous or unknown → routed to the backlog, **never guessed** (golden rule #5). This
   is not ML/NER — it is fully offline-testable.
3. **Run**: `make attributions-candidates` (needs the PISTE secret) writes the review backlog to
   `data/attributions/candidates/ministres_candidates.yaml` and prints coverage + match rate. The
   command exits nonzero below the match-rate floor.

### Promotion (human-in-the-loop)

The backlog is **never auto-loaded**. To publish a candidate:

1. Open `candidates/ministres_candidates.yaml`. For a `matched` row, open its `source_url` on
   Légifrance and confirm the décret is real, current, and targets the named ministry.
2. Copy a `MentionEntry`-shaped row into `ministres.yaml` using only `tutelle`, `legal_ref`,
   `source_url`, and `txt` — **drop the `entity_siren`** (it is re-resolved at build time via
   `ministeres.yaml`, golden rule #1/#5).
3. For an `unresolved` row, first add the missing ministry to the reviewed `ministeres.yaml`
   (with its `tutelle` code + verified SIREN), then promote as above.

Only after promotion does an attribution render on the fiche (« Attributions / mandat légal »).
