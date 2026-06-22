import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { IS_DEMO } from "../../lib/config";
import { buildFlowLinks, type SankeyLink } from "../../lib/flows";
import { euroCompact } from "../../lib/format";
import { mixesPerimeters } from "../../lib/perimeter";
import {
  Breadcrumb,
  DataTable,
  ExampleFlag,
  Flow,
  MethodologyNote,
  Sankey,
  Select,
  StateBlock,
  Warning,
  type DataTableColumn,
} from "../../lib/ui";
import { useFluxData } from "./useFluxData";

const TYPE_LABELS: Record<string, string> = {
  funds: "Financement",
  delegates: "Délégation",
  participation: "Participation",
};

const fluxColumns: DataTableColumn<SankeyLink & { key: string }>[] = [
  { key: "from", header: "De", render: (r) => r.sourceLabel, sortValue: (r) => r.sourceLabel },
  { key: "to", header: "Vers", render: (r) => r.targetLabel, sortValue: (r) => r.targetLabel },
  {
    key: "type",
    header: "Type",
    render: (r) => <span className="tag tag--sm">{TYPE_LABELS[r.type] ?? r.type}</span>,
  },
  {
    key: "value",
    header: "Montant",
    num: true,
    render: (r) => <span className="tnum">{euroCompact(r.value)}</span>,
    sortValue: (r) => r.value,
  },
  { key: "exercice", header: "Millésime", num: true, render: (r) => r.exercice ?? "—" },
];

export default function FluxPage() {
  const [params] = useSearchParams();
  const [focusSel, setFocusSel] = useState<string | null>(params.get("focus"));
  const flux = useFluxData(focusSel);

  const model = flux.status === "ready" ? flux.model : null;
  const root = model?.focusSiren ?? "";

  const links = useMemo(
    () => (model && root ? buildFlowLinks(root, model.edges, model.entityBySiren) : []),
    [model, root],
  );
  // Total tracé = the delegated amount flowing OUT of the focused buyer across the shown flows.
  const total = links.filter((l) => l.source === root).reduce((s, l) => s + l.value, 0);
  // When the traced flow touches more than one accounting universe (e.g. State LOLF + local M57),
  // the total is not a consolidated sum — surface the stronger mixed-perimeter caveat (FSC-42).
  const mixed = mixesPerimeters(links.flatMap((l) => [l.sourceLevel, l.targetLevel]));
  const rootName = model?.entityBySiren.get(root)?.name ?? "";
  const tableRows = links.map((l, i) => ({ ...l, key: `${l.source}-${l.target}-${i}` }));

  // The selector lists the top public buyers by delegated amount (real DECP flows). A ?focus= on a
  // buyer outside that list is surfaced as a selectable option too, so the control reflects it.
  // Fall back to the SIREN as the label when the name has not resolved yet, so the option always
  // matches `value={root}` and the selector never goes blank on a deep link.
  const delegators = model?.delegators ?? [];
  const knownFocus = delegators.some((d) => d.siren === root);
  const options =
    !knownFocus && root ? [{ siren: root, name: rootName || root }, ...delegators] : delegators;

  return (
    <div className="page fr-container">
      <div className="page-head">
        <Breadcrumb items={[{ label: "Accueil", to: "/" }, { label: "Flux de financement" }]} />
        <div className="section-head" style={{ marginTop: 12, marginBottom: 0 }}>
          <div className="section-head__title">
            <span className="eyebrow">Suivre l’argent</span>
            <h1 className="fr-h1">Flux de financement</h1>
          </div>
          <ExampleFlag>Montants d’exemple</ExampleFlag>
        </div>
        <p className="fr-lead" style={{ marginTop: 12, maxWidth: "70ch" }}>
          Les marchés et délégations publiés (DECP) d’un acheteur public vers ses titulaires. Les
          montants sont le <strong>montant global du marché</strong> (souvent un plafond
          d’accord-cadre, sur toute sa durée) — pas une dépense annuelle. Survolez un flux pour son
          détail.
        </p>
      </div>

      {flux.status === "error" ? (
        <StateBlock variant="error" icon={<Warning />} title="Flux indisponibles">
          La connexion aux données a échoué. Réessayez plus tard.
        </StateBlock>
      ) : (
        <>
          <div className="row-center wrap" style={{ marginBottom: 16, gap: 10 }}>
            <label className="field__label" htmlFor="flux-root">
              Focaliser sur :
            </label>
            <Select
              id="flux-root"
              style={{ maxWidth: 420 }}
              value={root}
              onChange={(e) => setFocusSel(e.target.value)}
            >
              {options.map((m) => (
                <option key={m.siren} value={m.siren}>
                  {m.name}
                </option>
              ))}
            </Select>
            <span className="fr-sm text-mention">
              Somme des {links.length} flux affichés :{" "}
              <strong className="tnum" style={{ color: "var(--grey-title)" }}>
                {euroCompact(total)}
              </strong>{" "}
              <span
                role="img"
                aria-label="Les plus gros marchés/délégations de cet acheteur — pas son total consolidé."
                title="Les plus gros marchés/délégations de cet acheteur — pas son total consolidé."
              >
                ⓘ
              </span>
            </span>
          </div>

          <div className="sankey-wrap">
            {links.length ? (
              <Sankey links={links} />
            ) : (
              <StateBlock icon={<Flow />} title="Aucun flux disponible">
                Cette entité ne publie pas de flux de financement vers des opérateurs dans le
                périmètre suivi.
              </StateBlock>
            )}
          </div>

          <div className="row-center wrap" style={{ gap: 16, marginTop: 12 }}>
            <span className="legend__row">
              <svg width="22" height="8" aria-hidden="true">
                <rect width="22" height="8" rx="2" fill="#0072b2" opacity="0.4" />
              </svg>{" "}
              Financement (subvention)
            </span>
            <span className="legend__row">
              <svg width="22" height="8" aria-hidden="true">
                <rect width="22" height="8" rx="2" fill="#e69f00" opacity="0.5" />
              </svg>{" "}
              Délégation / marché
            </span>
          </div>

          <MethodologyNote mixed={mixed} className="flux-methodology" />

          <h2 className="fr-h3" style={{ marginTop: 40, marginBottom: 16 }}>
            Équivalent tabulaire
          </h2>
          <DataTable
            caption={`Flux de financement — ${rootName}${IS_DEMO ? " (exemple)" : ""}`}
            columns={fluxColumns}
            rows={tableRows}
            getRowKey={(r) => r.key}
          />
        </>
      )}
    </div>
  );
}
