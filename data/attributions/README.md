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

## Scaling path: text → entity (FSC-66)

To scale beyond the editorial handful, drive the live pipeline (tracked in **FSC-66**):

1. **Discover** via the PISTE/Légifrance API (registry source `legifrance_attributions`,
   `platform: rest`). PISTE uses OAuth2 client-credentials — set `PISTE_CLIENT_ID` /
   `PISTE_CLIENT_SECRET` (see `.env.example`; server/CI only, never the frontend). The `rest`
   connector (`connectors/rest.py`) registers for this platform and documents the token flow.
2. **Search** LODA for "décret d'attribution" texts (consolidated since 1945); extract the
   competence articles and the ministry they target.
3. **Link** text → entity (the hard part): map the named ministry to its SIREN via the crosswalk.
   Where the text is ambiguous, route to the reviewed crosswalk backlog — **never guess**.
4. **Review**: a human validates each attribution before promotion (the "why" layer is a public
   trust signal, so precision over recall).

Full-text/NLP entity extraction is **not** run in CI today; the editorial file is the source of
truth until FSC-66 lands.
