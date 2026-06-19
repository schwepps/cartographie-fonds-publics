import { Fragment, useEffect, useMemo, useState, type ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { displayName } from "../../lib/acronyms";
import { IS_DEMO } from "../../lib/config";
import { euroCompact } from "../../lib/format";
import { LEVELS, type Level } from "../../lib/levels";
import { tutelleChain } from "../../lib/tutelle";
import {
  Badge,
  Breadcrumb,
  CheckRow,
  ExampleFlag,
  Field,
  LevelBadge,
  LevelShape,
  SearchBar,
  Select,
  StateBlock,
  Search as SearchIcon,
} from "../../lib/ui";
import { useSearch, type SearchEntity } from "./useSearch";

/** Wrap the first case-insensitive match of `q` in `text` with a <mark>. */
function highlight(text: string, q: string): ReactNode {
  if (!q) return text;
  const idx = text.toLowerCase().indexOf(q.toLowerCase());
  if (idx < 0) return text;
  return (
    <>
      {text.slice(0, idx)}
      <mark>{text.slice(idx, idx + q.length)}</mark>
      {text.slice(idx + q.length)}
    </>
  );
}

const ALL_LEVELS_ON: Record<Level, boolean> = {
  state: true,
  local: true,
  social: true,
  delegated: true,
};

// Stable empty fallbacks so the memo deps don't churn while the data loads.
const EMPTY_ENTITIES: SearchEntity[] = [];
const EMPTY_BY_SIREN = new Map<string, SearchEntity>();

export default function SearchPage() {
  const [params] = useSearchParams();
  const urlQuery = params.get("q")?.trim() ?? "";
  const [q, setQ] = useState(urlQuery);
  // `debouncedQ` drives the server-side fetch (useSearch) so we don't hit PostgREST on every
  // keystroke; `q` drives the controlled input + instant highlight.
  const [debouncedQ, setDebouncedQ] = useState(urlQuery);
  // Re-sync the controlled input when the URL ?q= changes (deep links, back/forward, a fresh header
  // search) — the React "adjust state during render" pattern, so typing stays free but navigation
  // wins. No effect (avoids the set-state-in-effect rule).
  const [lastUrlQuery, setLastUrlQuery] = useState(urlQuery);
  if (urlQuery !== lastUrlQuery) {
    setLastUrlQuery(urlQuery);
    setQ(urlQuery);
    setDebouncedQ(urlQuery); // a navigation deep-links straight to its results (no debounce wait)
  }
  useEffect(() => {
    if (q === debouncedQ) return;
    const timer = setTimeout(() => setDebouncedQ(q), 250);
    return () => clearTimeout(timer);
  }, [q, debouncedQ]);
  const search = useSearch(debouncedQ);
  const [levels, setLevels] = useState<Record<Level, boolean>>(ALL_LEVELS_ON);
  const [tutelle, setTutelle] = useState("all");
  // Default to name: per-entity budget magnitude is mostly absent on the curated data (PLF is
  // mission-level, not per-SIREN), so amount-sort would otherwise be an arbitrary tie-break.
  const [sort, setSort] = useState<"amount" | "name">("name");

  const ready = search.status === "ready";
  const entities = ready ? search.entities : EMPTY_ENTITIES;
  const bySiren = ready ? search.bySiren : EMPTY_BY_SIREN;
  const ministries = ready ? search.ministries : EMPTY_ENTITIES;

  // Text matching is done server-side (useSearch → search_entities RPC); here we only apply the
  // level + tutelle facets and the sort over the returned set.
  const results = useMemo(() => {
    const filtered = entities.filter((e) => {
      if (e.level && !levels[e.level as Level]) return false;
      if (tutelle !== "all") {
        const chain = tutelleChain(e.siren, bySiren);
        if (e.level !== "state" || chain[0]?.siren !== tutelle) return false;
      }
      return true;
    });
    return filtered.sort((a, b) =>
      sort === "amount" ? b.magnitude - a.magnitude : a.name.localeCompare(b.name, "fr"),
    );
  }, [entities, bySiren, levels, tutelle, sort]);

  const levelCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const level of Object.keys(LEVELS)) {
      counts[level] = entities.filter((e) => e.level === level).length;
    }
    return counts;
  }, [entities]);

  return (
    <div className="page fr-container">
      <div className="page-head">
        <Breadcrumb items={[{ label: "Accueil", to: "/" }, { label: "Recherche" }]} />
        <h1 className="fr-h1" style={{ marginTop: 12, marginBottom: 16 }}>
          Rechercher une institution
        </h1>
        <div style={{ maxWidth: 620 }}>
          <SearchBar
            value={q}
            onChange={setQ}
            label="Terme de recherche"
            placeholder="Nom d’une institution, d’un opérateur, d’un titulaire, un SIREN…"
          />
        </div>
      </div>

      {search.status === "error" ? (
        <StateBlock variant="error" icon={<SearchIcon />} title="Recherche indisponible">
          Le service de recherche n’a pas pu être chargé. Réessayez plus tard.
        </StateBlock>
      ) : (
        <div className="search-layout">
          <aside aria-label="Filtres">
            <div className="facet">
              <h2>Niveau</h2>
              {Object.values(LEVELS).map((meta) => (
                <CheckRow
                  key={meta.id}
                  checked={levels[meta.id as Level]}
                  onChange={(checked) => setLevels((prev) => ({ ...prev, [meta.id]: checked }))}
                  count={levelCounts[meta.id] ?? 0}
                >
                  <span className="row-center" style={{ gap: 6 }}>
                    <LevelShape level={meta.id} size={11} /> {meta.label}
                  </span>
                </CheckRow>
              ))}
            </div>
            <div className="facet">
              <Field label="Tutelle" htmlFor="search-tutelle">
                <Select
                  id="search-tutelle"
                  value={tutelle}
                  onChange={(e) => setTutelle(e.target.value)}
                >
                  <option value="all">Toutes</option>
                  {ministries.map((m) => (
                    <option key={m.siren} value={m.siren}>
                      {m.acronym ?? m.name}
                    </option>
                  ))}
                </Select>
              </Field>
            </div>
            <div className="facet">
              <h2>Trier par</h2>
              {(
                [
                  ["amount", "Montant (CP) décroissant"],
                  ["name", "Nom (A→Z)"],
                ] as const
              ).map(([key, label]) => (
                <label className="check-row" key={key}>
                  <input
                    type="radio"
                    name="sort"
                    checked={sort === key}
                    onChange={() => setSort(key)}
                  />
                  {label}
                </label>
              ))}
            </div>
          </aside>

          <div className="stack" style={{ gap: 12 }}>
            <div className="row-center" style={{ justifyContent: "space-between" }}>
              <p className="fr-sm text-mention" aria-live="polite">
                <strong style={{ color: "var(--grey-title)" }}>{results.length}</strong> résultat
                {results.length > 1 ? "s" : ""}
                {q ? <> pour « {q} »</> : null}
              </p>
              <ExampleFlag>Données d’exemple</ExampleFlag>
            </div>

            {results.length === 0 ? (
              <StateBlock icon={<SearchIcon />} title="Aucun résultat">
                Essayez un autre terme, élargissez les niveaux ou retirez le filtre de tutelle.
              </StateBlock>
            ) : (
              results.map((entity) => {
                const chain = tutelleChain(entity.siren, bySiren);
                return (
                  <Link key={entity.siren} className="result" to={`/entity/${entity.siren}`}>
                    <div style={{ minWidth: 0 }}>
                      <div className="row-center wrap" style={{ gap: 8, marginBottom: 6 }}>
                        <LevelBadge level={entity.level} />
                        {entity.category ? <Badge>{entity.category}</Badge> : null}
                      </div>
                      <div className="fr-h4" style={{ marginBottom: 4 }}>
                        {highlight(displayName(entity.siren, entity.name), q)}
                      </div>
                      <div className="breadcrumb fr-xs">
                        {chain.map((c, i) => (
                          <Fragment key={c.siren}>
                            {i > 0 ? <span className="breadcrumb__sep">›</span> : null}
                            <span>{c.acronym ?? c.name}</span>
                          </Fragment>
                        ))}
                      </div>
                    </div>
                    <div className="result__amount">
                      <div className="figure__value" style={{ fontSize: "1.25rem" }}>
                        {euroCompact(entity.magnitude || null)}
                      </div>
                      <div className="fr-xs text-mention">CP{IS_DEMO ? " · exemple" : ""}</div>
                    </div>
                  </Link>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}
