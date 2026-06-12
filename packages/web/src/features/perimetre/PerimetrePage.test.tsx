import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { axe } from "vitest-axe";
import PerimetrePage from "./PerimetrePage";

// Mock the read client: one per-level budget universe (lolf / m57 / social) + a contract for the
// delegated headline, plus a ministry→operator funds edge so the teaser Sankey lays out.
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
    ],
    budget_facts: [
      { exercice: 2025, amount_cp_eur: 15_279_000_000, executed: false, nomenclature: "lolf" },
      { exercice: 2023, amount_cp_eur: 5_000_000_000, executed: true, nomenclature: "m57" },
      // Older-year local row: must be EXCLUDED from the local headline (latest exercice only),
      // otherwise the figure would read 104 Md€ instead of 5 Md€.
      { exercice: 2021, amount_cp_eur: 99_000_000_000, executed: true, nomenclature: "m57" },
      // Voted (non-executed) local row in a LATER year: must be EXCLUDED (executed filter), else it
      // would both leak its amount in and push the latest exercice to 2024.
      { exercice: 2024, amount_cp_eur: 7_000_000_000, executed: false, nomenclature: "m57" },
      { exercice: 2023, amount_cp_eur: 245_000_000_000, executed: true, nomenclature: "social" },
    ],
    contracts: [{ montant_eur: 1_800_000, exercice: 2026 }],
  };
  const from = (table: string) => {
    const result = { data: data[table] ?? [], error: null, count: data[table]?.length ?? 0 };
    const builder = {
      select: () => builder,
      then: (resolve: (value: typeof result) => unknown) => Promise.resolve(result).then(resolve),
    };
    return builder;
  };
  return { supabase: { from, rpc: () => Promise.resolve({ data: [], error: null }) } };
});

const renderPage = () =>
  render(
    <MemoryRouter>
      <PerimetrePage />
    </MemoryRouter>,
  );

describe("PerimetrePage (Aperçu du périmètre)", () => {
  it("renders the page heading", async () => {
    renderPage();
    expect(
      await screen.findByRole("heading", { level: 1, name: "Aperçu du périmètre" }),
    ).toBeInTheDocument();
  });

  it("computes one headline figure per level in its own universe", async () => {
    renderPage();
    expect(await screen.findByText(/15,3\s*Md€/)).toBeInTheDocument(); // State (voted LOLF)
    expect(screen.getByText(/^5\s*Md€$/)).toBeInTheDocument(); // local (M57, latest year 2023 only)
    expect(screen.getByText(/245\s*Md€/)).toBeInTheDocument(); // social (LFSS, aggregated)
    expect(screen.getByText(/1,8\s*M€/)).toBeInTheDocument(); // delegated (DECP)
    // The older 2021 local row must not leak into the headline (would read 104 Md€), and the voted
    // 2024 row must not either (executed filter — would read 7 Md€ and shift the badge to 2024).
    expect(screen.queryByText(/104\s*Md€/)).not.toBeInTheDocument();
    expect(screen.queryByText(/^7\s*Md€$/)).not.toBeInTheDocument();
  });

  it("links each level to its detail view", async () => {
    renderPage();
    await screen.findByText(/15,3\s*Md€/);
    expect(screen.getByRole("link", { name: "Détail du périmètre État" })).toHaveAttribute(
      "href",
      "/graph",
    );
    expect(screen.getByRole("link", { name: "Détail du périmètre Local" })).toHaveAttribute(
      "href",
      "/flux",
    );
    expect(screen.getByRole("link", { name: "Détail du périmètre Social" })).toHaveAttribute(
      "href",
      "/sources#source-comptes_sociaux",
    );
    expect(screen.getByRole("link", { name: "Détail du périmètre Délégué" })).toHaveAttribute(
      "href",
      "/flux",
    );
  });

  it("surfaces the non-comparability + aggregated-social methodology notes", async () => {
    renderPage();
    await screen.findByText(/15,3\s*Md€/);
    expect(screen.getByText(/ordres de grandeur par sphère/i)).toBeInTheDocument();
    expect(screen.getByText(/module agrégé par branche/i)).toBeInTheDocument();
  });

  it("never renders a consolidated cross-universe total (anti-double-counting)", async () => {
    // FSC-58 / AC3: the four universes are shown as separate orders of magnitude. Their sum
    // (15,3 + 5 + 245 ≈ 265,3 Md€) must NEVER appear as a single figure — consolidating across
    // universes would double-count (ADR-0007). This guards against a regression that sums them.
    renderPage();
    await screen.findByText(/15,3\s*Md€/);
    expect(screen.queryByText(/265,3\s*Md€/)).not.toBeInTheDocument();
    expect(screen.queryByText(/^265\s*Md€$/)).not.toBeInTheDocument();
    // …and the convention is stated explicitly (lead + methodology note), not merely implied.
    expect(screen.getAllByText(/jamais une somme consolidée/i).length).toBeGreaterThan(0);
  });

  it("does not fold a State→local funds transfer into the State headline (AC1)", async () => {
    // The mock carries a 2,95 Md€ funds edge (ministry→operator). It is a *flow* (it feeds the
    // teaser Sankey), not a budget fact — so the State headline stays the voted LOLF total
    // (15,3 Md€) and never the inflated 18,2 Md€ (15,3 + 2,95). A transfer can't double-count.
    renderPage();
    expect(await screen.findByText(/15,3\s*Md€/)).toBeInTheDocument();
    expect(screen.queryByText(/18,2\s*Md€/)).not.toBeInTheDocument();
  });

  it("renders the teaser Sankey once flows load", async () => {
    const { container } = renderPage();
    await screen.findByText(/15,3\s*Md€/);
    expect(container.querySelector("svg[role='img']")).not.toBeNull();
  });

  it("has no accessibility violations", async () => {
    const { container } = renderPage();
    await screen.findByText(/15,3\s*Md€/);
    expect(await axe(container)).toHaveNoViolations();
  });
});
