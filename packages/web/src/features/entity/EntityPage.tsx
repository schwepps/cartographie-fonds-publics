import { useMemo, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams } from "react-router-dom";
import { acronymOf } from "../../lib/acronyms";
import { euroCompact, euroFull } from "../../lib/format";
import { UNIVERSE_LOLF, universeForLevel } from "../../lib/perimeter";
import { seqColor } from "../../lib/seq";
import { tutelleChain, type ChainEntity } from "../../lib/tutelle";
import { ProvenanceBadge } from "../../lib/provenance/ProvenanceBadge";
import { allSources } from "../../lib/provenance/sources";
import {
  Arrow,
  Bars,
  Breadcrumb,
  Button,
  Callout,
  Card,
  Chip,
  DataTable,
  ExampleFlag,
  External,
  Flow,
  Graph as GraphIcon,
  LevelBadge,
  LevelShape,
  MethodologyNote,
  Spark,
  StateBlock,
  Warning,
  type DataTableColumn,
} from "../../lib/ui";
import type { BudgetFactRow, ContractRow, MentionRow, RelatedEntity } from "./types";
import { useEntitySheet } from "./useEntitySheet";

/** Accept only http(s) URLs so a `javascript:`/`data:` URL can never reach an `href` (RGAA + XSS). */
function safeHttpUrl(raw: string | null | undefined): string | null {
  if (!raw) return null;
  try {
    const u = new URL(raw);
    return u.protocol === "http:" || u.protocol === "https:" ? u.href : null;
  } catch {
    return null;
  }
}

/** Long French date (day month year); ISO parsed as UTC so the day never shifts across time zones. */
function frDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("fr-FR", {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  });
}

/** Display label for a mention type; an unknown/NULL value (legacy rows) is never mislabeled. */
function mentionTypeLabel(type: string | null): string {
  if (type === "recommandation") return "Recommandation";
  if (type === "rapport") return "Rapport";
  return "—";
}

/** External link with the DSFR/RGAA "new window" affordance (visually-hidden warning + icon). */
function ExtLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a className="fr-link" href={href} target="_blank" rel="noopener noreferrer">
      {children} <External style={{ width: 14, height: 14 }} />
      <span className="sr-only"> (nouvelle fenêtre)</span>
    </a>
  );
}

function MissionBars({ rows }: { rows: BudgetFactRow[] }) {
  if (!rows.length) return null;
  const max = Math.max(...rows.map((r) => r.amount_cp_eur ?? 0), 1);
  return (
    <Bars
      max={max}
      items={rows.map((r) => ({
        label: r.programme ?? r.mission ?? "—",
        value: r.amount_cp_eur ?? 0,
        amount: euroCompact(r.amount_cp_eur),
        color: seqColor(0.4 + 0.5 * ((r.amount_cp_eur ?? 0) / max)),
      }))}
    />
  );
}

function TrendSpark({ budget }: { budget: BudgetFactRow[] }) {
  const byYear = new Map<number, number>();
  for (const b of budget) {
    if (b.executed) continue;
    byYear.set(b.exercice, (byYear.get(b.exercice) ?? 0) + (b.amount_cp_eur ?? 0));
  }
  const years = [...byYear.keys()].sort((a, b) => a - b);
  if (years.length < 2) return null;
  const current = years[years.length - 1];
  return (
    <Spark
      ariaLabel="Tendance pluriannuelle des crédits de paiement"
      points={years.map((y) => ({
        label: String(y),
        value: byYear.get(y) ?? 0,
        current: y === current,
      }))}
    />
  );
}

export default function EntityPage() {
  const { siren = "" } = useParams<{ siren: string }>();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const state = useEntitySheet(siren);

  const entity = state.status === "ready" ? state.entity : null;
  const chain = useMemo(() => {
    if (!entity) return [];
    const byId = new Map<string, ChainEntity & RelatedEntity>();
    byId.set(entity.siren, { ...entity });
    if (state.status === "ready") for (const r of state.related.values()) byId.set(r.siren, r);
    return tutelleChain<ChainEntity & RelatedEntity>(entity.siren, byId);
  }, [entity, state]);

  if (state.status === "loading") {
    return (
      <div className="page fr-container">
        <StateBlock title="Chargement de l’entité…">Récupération de la fiche…</StateBlock>
      </div>
    );
  }
  if (state.status === "error") {
    return (
      <div className="page fr-container">
        <StateBlock variant="error" icon={<Warning />} title="Impossible de charger cette entité">
          Réessayez plus tard.
        </StateBlock>
      </div>
    );
  }
  if (!entity) {
    return (
      <div className="page fr-container">
        <StateBlock icon={<Warning />} title="Entité introuvable">
          Aucune institution ne correspond au SIREN {siren}.
        </StateBlock>
      </div>
    );
  }

  const { edges, budgetFacts, children, contracts, attributions, mentions, related } = state;
  const nameOf = (s: string) => related.get(s)?.name ?? s;
  const levelOf = (s: string) => related.get(s)?.level ?? null;

  const exercices = [...new Set(budgetFacts.map((b) => b.exercice))].sort((a, b) => b - a);
  const lastEx = exercices[0];
  // State/LOLF sheets show *voté* credits (AE/CP) when the latest exercice has them. Local (M57) and
  // social facts are realised (executed=true) and cash-basis; a State exercice with execution data
  // only is realised too — in both cases fall back to the realised figure rather than render an
  // empty 0 €. Only the non-LOLF case also carries the accounting-universe note (FSC-42).
  const isLolfBudget = universeForLevel(entity.level) === UNIVERSE_LOLF;
  const lastFacts = budgetFacts.filter((b) => b.exercice === lastEx);
  const votedLast = lastFacts.filter((b) => !b.executed);
  const showVoted = isLolfBudget && votedLast.length > 0;
  const figureFacts = showVoted ? votedLast : lastFacts;
  const totalAe = figureFacts.reduce((s, b) => s + (b.amount_ae_eur ?? 0), 0);
  const totalCp = figureFacts.reduce((s, b) => s + (b.amount_cp_eur ?? 0), 0);
  const budgetProvenance = isLolfBudget
    ? "budget_plf_lfi"
    : entity.level === "social"
      ? "comptes_sociaux"
      : "finances_locales_ofgl";

  const out = edges
    .filter(
      (e) =>
        e.source_siren === siren && (e.type === "funds" || e.type === "delegates") && e.amount_eur,
    )
    .sort((a, b) => (b.amount_eur ?? 0) - (a.amount_eur ?? 0));
  const fundedOps = out.filter((o) => o.type === "funds").slice(0, 6);
  const outMax = out[0]?.amount_eur ?? 1;

  const src = entity.provenance ? allSources().find((s) => s.id === entity.provenance) : undefined;

  const budgetCols: DataTableColumn<BudgetFactRow>[] = [
    { key: "exercice", header: "Millésime", num: true },
    { key: "mission", header: "Mission", render: (r) => r.mission ?? "—" },
    { key: "programme", header: "Programme", render: (r) => r.programme ?? "—" },
    {
      key: "ae",
      header: "AE",
      num: true,
      render: (r) => <span className="tnum">{euroCompact(r.amount_ae_eur)}</span>,
      sortValue: (r) => r.amount_ae_eur ?? 0,
    },
    {
      key: "cp",
      header: "CP",
      num: true,
      render: (r) => <span className="tnum">{euroCompact(r.amount_cp_eur)}</span>,
      sortValue: (r) => r.amount_cp_eur ?? 0,
    },
    {
      key: "status",
      header: "Statut",
      render: (r) => (
        <span className={`badge ${r.executed ? "badge--success" : "badge--blue"}`}>
          {r.executed ? "Exécuté" : "Voté"}
        </span>
      ),
    },
  ];

  const contractCols: DataTableColumn<ContractRow>[] = [
    {
      key: "titulaire",
      header: "Titulaire",
      render: (r) => {
        const other = r.acheteur_siren === siren ? r.titulaire_siren : r.acheteur_siren;
        return other ? (
          <Link className="fr-link" to={`/entity/${other}`}>
            {nameOf(other)}
          </Link>
        ) : (
          "—"
        );
      },
    },
    {
      key: "nature",
      header: "Nature",
      render: (r) => (
        <span className="tag tag--sm">{r.nature === "marche" ? "Marché" : "Concession"}</span>
      ),
    },
    {
      key: "montant",
      header: "Montant",
      num: true,
      render: (r) => <span className="tnum">{euroFull(r.montant_eur)}</span>,
      sortValue: (r) => r.montant_eur ?? 0,
    },
    { key: "exercice", header: "Millésime", num: true, render: (r) => r.exercice ?? "—" },
  ];

  const mentionCols: DataTableColumn<MentionRow>[] = [
    {
      key: "report_date",
      header: "Date",
      num: true,
      render: (r) => frDate(r.report_date),
      sortValue: (r) => r.report_date ?? "",
    },
    {
      key: "mention_type",
      header: "Type",
      render: (r) => <span className="tag tag--sm">{mentionTypeLabel(r.mention_type)}</span>,
    },
    {
      key: "report_ref",
      header: "Référence",
      sortable: false,
      render: (r) => {
        const href = safeHttpUrl(r.url);
        return href ? (
          <ExtLink href={href}>{r.report_ref ?? "Source"}</ExtLink>
        ) : (
          (r.report_ref ?? "—")
        );
      },
    },
    {
      key: "note",
      header: "Extrait",
      sortable: false,
      render: (r) => <span className="fr-sm">{r.note ?? "—"}</span>,
    },
  ];

  return (
    <div className="page fr-container">
      <div className="page-head">
        <Breadcrumb
          items={[
            { label: "Accueil", to: "/" },
            { label: "Graphe", to: "/graph" },
            ...chain.map((c) => ({
              label: acronymOf(c.siren) ?? c.name,
              to: c.siren === siren ? undefined : `/entity/${c.siren}`,
            })),
          ]}
        />
      </div>

      <div className="identity-head" style={{ marginBottom: 28 }}>
        <div style={{ maxWidth: "62ch" }}>
          <div className="row-center wrap" style={{ gap: 8, marginBottom: 12 }}>
            <LevelBadge level={entity.level} />
            {entity.category ? <span className="badge">{entity.category}</span> : null}
            <ExampleFlag>Exemple</ExampleFlag>
          </div>
          <h1 className="fr-h1" style={{ marginBottom: 10 }}>
            {entity.name}
          </h1>
          <dl className="kv" style={{ maxWidth: 520 }}>
            <dt>SIREN</dt>
            <dd>
              <span className="mono">{entity.siren}</span>
            </dd>
            <dt>Tutelle</dt>
            <dd>
              {entity.parent_siren ? (
                <Link className="fr-link" to={`/entity/${entity.parent_siren}`}>
                  {nameOf(entity.parent_siren)}
                </Link>
              ) : (
                <span className="text-mention">Administration centrale (sans tutelle)</span>
              )}
            </dd>
          </dl>
        </div>
        <div className="row wrap" style={{ gap: 8, alignItems: "flex-start" }}>
          <Button variant="secondary" onClick={() => navigate("/graph")}>
            <GraphIcon /> Voir dans le graphe
          </Button>
          <Button variant="primary" onClick={() => navigate(`/flux?focus=${siren}`)}>
            <Flow /> Flux
          </Button>
        </div>
      </div>

      <div className="sheet-grid">
        <div className="stack" style={{ gap: 32 }}>
          <section>
            <div className="section-head" style={{ marginBottom: 16 }}>
              <div className="section-head__title">
                <span className="eyebrow">Budget</span>
                <h2 className="fr-h3">Crédits — exercice {lastEx ?? "n.d."}</h2>
              </div>
            </div>
            {budgetFacts.length ? (
              <>
                <div
                  className="grid"
                  style={{
                    gridTemplateColumns: showVoted ? "1fr 1fr" : "1fr",
                    gap: 16,
                    marginBottom: 20,
                  }}
                >
                  {showVoted ? (
                    <div className="figure" style={{ borderTopColor: "var(--niv-etat)" }}>
                      <div
                        className="fr-xs text-mention"
                        style={{ textTransform: "uppercase", letterSpacing: ".04em" }}
                      >
                        Autorisations d’engagement (AE) · voté
                      </div>
                      <div className="figure__value" style={{ fontSize: "1.7rem" }}>
                        {euroCompact(totalAe)}
                      </div>
                    </div>
                  ) : null}
                  <div className="figure">
                    <div
                      className="fr-xs text-mention"
                      style={{ textTransform: "uppercase", letterSpacing: ".04em" }}
                    >
                      {showVoted
                        ? "Crédits de paiement (CP) · voté"
                        : "Dépenses réelles (CP) · réalisé"}
                    </div>
                    <div className="figure__value" style={{ fontSize: "1.7rem" }}>
                      {euroCompact(totalCp)}
                    </div>
                  </div>
                </div>
                {!isLolfBudget ? (
                  <MethodologyNote className="entity-methodology">
                    {/* The M57/M14 wording fits local only; other non-LOLF universes (e.g. social)
                        fall back to the generic double-counting disclaimer. */}
                    {entity.level === "local" ? t("methodology.local") : undefined}
                  </MethodologyNote>
                ) : null}
                <div
                  className="grid"
                  style={{ gridTemplateColumns: "1.4fr 1fr", gap: 28, alignItems: "start" }}
                >
                  <div>
                    <div className="fr-sm" style={{ fontWeight: 600, marginBottom: 10 }}>
                      Répartition par programme (CP {showVoted ? "voté" : "réalisé"} {lastEx})
                    </div>
                    <MissionBars rows={figureFacts} />
                  </div>
                  {exercices.length > 1 ? (
                    <div>
                      <div className="fr-sm" style={{ fontWeight: 600, marginBottom: 10 }}>
                        Tendance pluriannuelle (CP)
                      </div>
                      <TrendSpark budget={budgetFacts} />
                    </div>
                  ) : null}
                </div>
                <details style={{ marginTop: 20 }}>
                  <summary className="fr-link" style={{ cursor: "pointer" }}>
                    Détail par mission / programme (AE/CP, voté &amp; exécuté)
                  </summary>
                  <div style={{ marginTop: 12 }}>
                    <DataTable
                      caption={`Crédits budgétaires — ${entity.name}`}
                      columns={budgetCols}
                      rows={budgetFacts}
                      getRowKey={(r) => `${r.exercice}|${r.programme}|${r.executed}`}
                    />
                  </div>
                </details>
                <div style={{ marginTop: 10 }}>
                  <ProvenanceBadge provenanceId={budgetProvenance} millesime={lastEx} />
                </div>
              </>
            ) : (
              <Callout>
                <p className="fr-sm">
                  Aucun crédit budgétaire directement attribué à cette entité dans le périmètre
                  suivi. Son financement apparaît côté{" "}
                  <Link className="fr-link" to={`/flux?focus=${siren}`}>
                    flux
                  </Link>{" "}
                  (subvention de sa tutelle).
                </p>
              </Callout>
            )}
          </section>

          {entity.level === "state" ? (
            <section>
              <div className="section-head" style={{ marginBottom: 16 }}>
                <div className="section-head__title">
                  <span className="eyebrow">Cadre juridique</span>
                  <h2 className="fr-h3">Attributions / mandat légal</h2>
                </div>
              </div>
              {attributions.length ? (
                <>
                  <ul
                    className="stack"
                    style={{ gap: 14, listStyle: "none", padding: 0, margin: 0 }}
                  >
                    {attributions.map((a, i) => {
                      const href = safeHttpUrl(a.source_url);
                      return (
                        <li key={`${a.legal_ref ?? "ref"}|${i}`}>
                          {a.txt ? (
                            <p className="fr-sm" style={{ margin: "0 0 4px" }}>
                              {a.txt}
                            </p>
                          ) : null}
                          <div className="fr-xs text-mention">
                            {href ? (
                              <ExtLink href={href}>{a.legal_ref ?? "Référence légale"}</ExtLink>
                            ) : (
                              <span>{a.legal_ref ?? "—"}</span>
                            )}
                          </div>
                        </li>
                      );
                    })}
                  </ul>
                  {attributions[0]?.provenance ? (
                    <div style={{ marginTop: 12 }}>
                      <ProvenanceBadge provenanceId={attributions[0].provenance} />
                    </div>
                  ) : null}
                </>
              ) : (
                <Callout>
                  <p className="fr-sm">Aucune attribution légale renseignée pour cette entité.</p>
                </Callout>
              )}
            </section>
          ) : null}

          {out.length ? (
            <section>
              <div className="section-head" style={{ marginBottom: 16 }}>
                <div className="section-head__title">
                  <span className="eyebrow">Suivre l’argent</span>
                  <h2 className="fr-h3">Où va son argent</h2>
                </div>
                <Link className="fr-link" to={`/flux?focus=${siren}`}>
                  Diagramme complet <Arrow style={{ width: 15, height: 15 }} />
                </Link>
              </div>
              <Bars
                max={outMax}
                items={out.slice(0, 6).map((o) => ({
                  label: (
                    <Link className="fr-link" to={`/entity/${o.target_siren}`}>
                      {nameOf(o.target_siren)}
                    </Link>
                  ),
                  value: o.amount_eur ?? 0,
                  amount: euroCompact(o.amount_eur),
                  color: o.type === "delegates" ? "var(--niv-delegue)" : "var(--seq-5)",
                }))}
              />
            </section>
          ) : null}

          {contracts.length ? (
            <section>
              <div className="section-head" style={{ marginBottom: 16 }}>
                <div className="section-head__title">
                  <span className="eyebrow">Commande publique</span>
                  <h2 className="fr-h3">Principaux titulaires</h2>
                </div>
              </div>
              <DataTable
                caption={`Contrats (DECP) — ${entity.name}`}
                columns={contractCols}
                rows={contracts}
                getRowKey={(r) => `${r.titulaire_siren}|${r.montant_eur}|${r.exercice}`}
              />
              <div style={{ marginTop: 10 }}>
                <ProvenanceBadge provenanceId="decp_commande_publique" millesime={2026} />
              </div>
            </section>
          ) : null}

          <section>
            <div className="section-head" style={{ marginBottom: 16 }}>
              <div className="section-head__title">
                <span className="eyebrow">Contrôle</span>
                <h2 className="fr-h3">Cour des comptes</h2>
              </div>
            </div>
            {mentions.length ? (
              <>
                <DataTable
                  caption={`Mentions Cour des comptes — ${entity.name}`}
                  columns={mentionCols}
                  rows={mentions}
                  getRowKey={(r) => `${r.report_ref}|${r.report_date}|${r.mention_type}`}
                />
                {mentions[0]?.provenance ? (
                  <div style={{ marginTop: 10 }}>
                    <ProvenanceBadge provenanceId={mentions[0].provenance} />
                  </div>
                ) : null}
              </>
            ) : (
              <Callout>
                <p className="fr-sm">
                  Aucune mention de la Cour des comptes recensée pour cette entité dans le périmètre
                  suivi.
                </p>
              </Callout>
            )}
          </section>
        </div>

        <aside className="stack" style={{ gap: 20 }}>
          <Card pad topBorder>
            <div
              className="fr-xs text-mention"
              style={{ textTransform: "uppercase", letterSpacing: ".04em", marginBottom: 8 }}
            >
              Chaîne de tutelle
            </div>
            <ol style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {chain.map((c, i) => (
                <li key={c.siren} className="row-center" style={{ gap: 8, paddingLeft: i * 14 }}>
                  {i > 0 ? <span className="text-mention">└</span> : null}
                  <LevelShape level={c.level} size={11} />
                  {c.siren === siren ? (
                    <strong className="fr-sm">{c.name}</strong>
                  ) : (
                    <Link className="fr-link fr-sm" to={`/entity/${c.siren}`}>
                      {c.name}
                    </Link>
                  )}
                </li>
              ))}
            </ol>
          </Card>

          {children.length ? (
            <Card pad>
              <div
                className="fr-xs text-mention"
                style={{ textTransform: "uppercase", letterSpacing: ".04em", marginBottom: 8 }}
              >
                Opérateurs sous tutelle ({children.length})
              </div>
              <div className="row wrap" style={{ gap: 6 }}>
                {children.map((c) => (
                  <Chip
                    key={c.siren}
                    small
                    level={c.level}
                    onClick={() => navigate(`/entity/${c.siren}`)}
                  >
                    {acronymOf(c.siren) ?? c.name}
                  </Chip>
                ))}
              </div>
            </Card>
          ) : null}

          {fundedOps.length ? (
            <Card pad>
              <div
                className="fr-xs text-mention"
                style={{ textTransform: "uppercase", letterSpacing: ".04em", marginBottom: 8 }}
              >
                Opérateurs financés
              </div>
              <div className="row wrap" style={{ gap: 6 }}>
                {fundedOps.map((o) => (
                  <Chip
                    key={o.target_siren}
                    small
                    level={levelOf(o.target_siren)}
                    onClick={() => navigate(`/entity/${o.target_siren}`)}
                  >
                    {acronymOf(o.target_siren) ?? nameOf(o.target_siren)}
                  </Chip>
                ))}
              </div>
            </Card>
          ) : null}

          <Card pad style={{ background: "var(--bg-alt)" }}>
            <div
              className="fr-xs text-mention"
              style={{ textTransform: "uppercase", letterSpacing: ".04em", marginBottom: 8 }}
            >
              Provenance
            </div>
            <dl className="kv" style={{ gridTemplateColumns: "90px 1fr", fontSize: "0.8125rem" }}>
              <dt>Source</dt>
              <dd>{src ? src.publisher.split("—")[0].trim() : "—"}</dd>
              <dt>Licence</dt>
              <dd>{src ? src.licence : "—"}</dd>
              <dt>Cadence</dt>
              <dd>{src ? src.cadence : "—"}</dd>
            </dl>
            <Link
              className="fr-link fr-sm"
              to="/sources"
              style={{ marginTop: 10, display: "inline-flex" }}
            >
              Détail de la source <Arrow style={{ width: 14, height: 14 }} />
            </Link>
          </Card>
        </aside>
      </div>
    </div>
  );
}
