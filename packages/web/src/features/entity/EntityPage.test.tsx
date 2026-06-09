import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { axe } from "vitest-axe";
import EntityPage from "./EntityPage";

const MESR = "110044013";

// Models the entity-sheet queries: entity (eq+maybeSingle), edges (or), budget (eq), children
// (eq parent_siren), contracts (eq acheteur), related (in). The builder tracks the last filter so a
// table queried several ways (entities) resolves to the right slice.
// The mock factory is hoisted above the module body, so it inlines the SIRENs rather than the outer
// MESR/CNRS consts (which aren't initialised yet at hoist time).
vi.mock("../../lib/supabase", () => {
  const entityRows: Record<string, Record<string, unknown>> = {
    "110044013": {
      siren: "110044013",
      name: "Ministère de l’ESR",
      level: "state",
      category: "ministère",
      parent_siren: null,
      provenance: "operateurs_etat",
    },
    "180089013": {
      siren: "180089013",
      name: "Centre national de la recherche scientifique",
      level: "state",
      category: "EPST",
      parent_siren: "110044013",
      provenance: "operateurs_etat",
    },
  };
  const edges = [
    {
      source_siren: "110044013",
      target_siren: "180089013",
      type: "funds",
      amount_eur: 2_950_000_000,
      exercice: 2025,
      provenance: "budget_plf_lfi",
    },
  ];
  const budget = [
    {
      exercice: 2025,
      mission: "MIRES",
      programme: "150 — Formations",
      amount_ae_eur: 15_217_000_000,
      amount_cp_eur: 15_279_000_000,
      executed: false,
    },
    {
      exercice: 2024,
      mission: "MIRES",
      programme: "150 — Formations",
      amount_ae_eur: 14_690_000_000,
      amount_cp_eur: 14_710_000_000,
      executed: true,
    },
  ];
  const contracts = [
    {
      acheteur_siren: "110044013",
      titulaire_siren: "329200521",
      montant_eur: 1_800_000,
      nature: "marche",
      exercice: 2026,
    },
  ];

  const from = (table: string) => {
    const filter: { col?: string; val?: unknown; inVals?: string[] } = {};
    const resolveMany = () => {
      if (table === "edges") return edges;
      if (table === "budget_facts") return budget;
      if (table === "contracts") return contracts;
      if (table === "entities") {
        if (filter.inVals) return filter.inVals.map((s) => entityRows[s]).filter(Boolean);
        if (filter.col === "parent_siren") {
          return Object.values(entityRows).filter((e) => e.parent_siren === filter.val);
        }
      }
      return [];
    };
    const builder = {
      select: () => builder,
      eq: (col: string, val: unknown) => {
        filter.col = col;
        filter.val = val;
        return builder;
      },
      or: () => builder,
      in: (_col: string, vals: string[]) => {
        filter.inVals = vals;
        return builder;
      },
      maybeSingle: () =>
        Promise.resolve({ data: entityRows[String(filter.val)] ?? null, error: null }),
      then: (resolve: (value: { data: unknown[]; error: null }) => unknown) =>
        Promise.resolve({ data: resolveMany(), error: null }).then(resolve),
    };
    return builder;
  };
  return { supabase: { from } };
});

const renderSheet = (siren: string) =>
  render(
    <MemoryRouter initialEntries={[`/entity/${siren}`]}>
      <Routes>
        <Route path="/entity/:siren" element={<EntityPage />} />
      </Routes>
    </MemoryRouter>,
  );

describe("EntityPage (fiche)", () => {
  it("renders the identity header with badges", async () => {
    renderSheet(MESR);
    expect(
      await screen.findByRole("heading", { level: 1, name: /Ministère de l’ESR/ }),
    ).toBeInTheDocument();
    expect(screen.getByText("ministère")).toBeInTheDocument();
  });

  it("shows the voted AE/CP budget figures and the per-programme bars", async () => {
    renderSheet(MESR);
    await screen.findByRole("heading", { level: 1 });
    expect(screen.getByText(/Autorisations d’engagement/)).toBeInTheDocument();
    expect(screen.getByText(/Répartition par programme/)).toBeInTheDocument();
    // The programme appears in the bar + the details table.
    expect(screen.getAllByText(/150 — Formations/).length).toBeGreaterThan(0);
  });

  it("lists supervised operators as chips linking to their sheets", async () => {
    renderSheet(MESR);
    await screen.findByRole("heading", { level: 1 });
    const card = screen.getByText(/Opérateurs sous tutelle/).closest(".card") as HTMLElement;
    // CNRS appears in both the tutelle card and the funded-operators card; scope to the tutelle one.
    expect(within(card).getByRole("button", { name: /CNRS/ })).toBeInTheDocument();
  });

  it("renders the contracts table (principaux titulaires)", async () => {
    renderSheet(MESR);
    await screen.findByRole("heading", { level: 1 });
    const table = await screen.findByRole("table", { name: /Contrats \(DECP\)/ });
    expect(within(table).getByText(/329200521/)).toBeInTheDocument();
  });

  it("has no accessibility violations", async () => {
    const { container } = renderSheet(MESR);
    await screen.findByRole("heading", { level: 1 });
    expect(await axe(container)).toHaveNoViolations();
  });
});
