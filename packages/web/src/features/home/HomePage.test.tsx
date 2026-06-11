import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { axe } from "vitest-axe";
import HomePage from "./HomePage";

// Mock the read client: entities (count + operator filter), edges (teaser flows), budget (CP sum),
// contracts (count head). The teaser is built for the ESR ministry 110044013.
vi.mock("../../lib/supabase", () => {
  const data: Record<string, unknown[]> = {
    entities: [
      { siren: "110044013", name: "Ministère de la Recherche", level: "state", parent_siren: null },
      { siren: "180089013", name: "CNRS", level: "state", parent_siren: "110044013" },
    ],
    edges: [
      {
        source_siren: "110044013",
        target_siren: "180089013",
        type: "funds",
        amount_eur: 2_950_000_000,
        exercice: 2025,
      },
      {
        source_siren: "180089013",
        target_siren: "329200521",
        type: "delegates",
        amount_eur: 1_800_000,
        exercice: 2026,
      },
    ],
    budget_facts: [
      { exercice: 2025, amount_cp_eur: 15_279_000_000, executed: false, nomenclature: "lolf" },
    ],
    contracts: [],
  };
  const from = (table: string) => {
    const result = {
      data: data[table] ?? [],
      error: null,
      count: table === "contracts" ? 6 : (data[table]?.length ?? 0),
    };
    const builder = {
      select: () => builder,
      then: (resolve: (value: typeof result) => unknown) => Promise.resolve(result).then(resolve),
    };
    return builder;
  };
  return { supabase: { from, rpc: () => Promise.resolve({ data: [], error: null }) } };
});

const renderHome = () =>
  render(
    <MemoryRouter>
      <HomePage />
    </MemoryRouter>,
  );

describe("HomePage (Accueil)", () => {
  it("renders the hero with the primary CTAs (exact names disambiguate the tiles)", () => {
    renderHome();
    expect(
      screen.getByRole("heading", { level: 1, name: /Comprendre où va/i }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Explorer le graphe" })).toHaveAttribute(
      "href",
      "/graph",
    );
    expect(screen.getByRole("link", { name: "Rechercher" })).toHaveAttribute("href", "/search");
  });

  it("computes the headline figures from Supabase", async () => {
    renderHome();
    // budget CP 15,279 Md → "15,3 Md€"; 2 institutions; 1 operator (CNRS has a parent); 6 contracts.
    expect(await screen.findByText(/15,3\s*Md€/)).toBeInTheDocument();
    expect(screen.getByText("Institutions cartographiées")).toBeInTheDocument();
    expect(screen.getByText("Contrats publics reliés")).toBeInTheDocument();
  });

  it("renders the three action tiles linking to the features", () => {
    renderHome();
    const tile = (desc: RegExp, href: string) => {
      const link = screen.getByText(desc).closest("a");
      expect(link).toHaveAttribute("href", href);
    };
    tile(/Naviguez le réseau des institutions/, "/graph");
    tile(/Trouvez un ministère, un opérateur/, "/search");
    tile(/Du financeur public au titulaire/, "/flux");
  });

  it("renders the teaser Sankey once flows load", async () => {
    const { container } = renderHome();
    await screen.findByText(/15,3\s*Md€/);
    expect(container.querySelector("svg[role='img']")).not.toBeNull();
  });

  it("has no accessibility violations", async () => {
    const { container } = renderHome();
    await screen.findByText(/15,3\s*Md€/);
    expect(await axe(container)).toHaveNoViolations();
  });
});

describe("HomePage trust strip", () => {
  it("lists the open-data trust items", () => {
    renderHome();
    const strip = screen.getByText("Données ouvertes").closest(".trust-strip") as HTMLElement;
    expect(within(strip).getByText("Données ouvertes")).toBeInTheDocument();
    expect(within(strip).getByText("Licences tracées")).toBeInTheDocument();
    expect(within(strip).getByText("Méthodologie publiée")).toBeInTheDocument();
  });
});
