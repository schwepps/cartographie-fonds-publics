import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { axe } from "vitest-axe";

// jsdom has no 2D canvas, so the force renderer no-ops (it guards on a null context); these tests
// assert the data layer, the live counts and the accessible table fallback. The canvas is verified
// manually against the design.
vi.mock("../../lib/supabase", () => {
  const data: Record<string, unknown[]> = {
    entities: [
      {
        siren: "110044013",
        name: "MESR",
        level: "state",
        category: "ministère",
        parent_siren: null,
      },
      {
        siren: "180089013",
        name: "Centre national de la recherche scientifique",
        level: "state",
        category: "EPST",
        parent_siren: "110044013",
      },
    ],
    edges: [
      {
        source_siren: "110044013",
        target_siren: "180089013",
        type: "tutelle",
        amount_eur: null,
        exercice: null,
      },
      {
        source_siren: "110044013",
        target_siren: "180089013",
        type: "funds",
        amount_eur: 2_950_000_000,
        exercice: 2025,
      },
    ],
    budget_facts: [
      { entity_siren: "110044013", exercice: 2025, amount_cp_eur: 26_000_000_000, executed: false },
    ],
  };
  const from = (table: string) => {
    const result = { data: data[table] ?? [], error: null };
    const builder = {
      select: () => builder,
      limit: () => builder,
      then: (resolve: (value: typeof result) => unknown) => Promise.resolve(result).then(resolve),
    };
    return builder;
  };
  return { supabase: { from } };
});

import GraphPage from "./GraphPage";

const renderGraph = () =>
  render(
    <MemoryRouter>
      <GraphPage />
    </MemoryRouter>,
  );

describe("GraphPage (institutional graph)", () => {
  it("shows live counts in the toolbar once the model loads", async () => {
    renderGraph();
    expect(await screen.findByText(/institutions affichées sur/)).toBeInTheDocument();
  });

  it("provides a synchronized accessible table fallback linking to sheets", async () => {
    renderGraph();
    await screen.findByText(/institutions affichées sur/);
    const toggle = screen.getByRole("group", { name: /Mode d’affichage/ });
    await userEvent.click(within(toggle).getByRole("button", { name: /Vue tableau/ }));
    const table = await screen.findByRole("table", { name: /Institutions affichées/ });
    expect(
      within(table).getByRole("link", { name: /Centre national de la recherche scientifique/ }),
    ).toHaveAttribute("href", "/entity/180089013");
  });

  it("documents keyboard navigation for accessibility", async () => {
    renderGraph();
    expect(await screen.findByText(/navigable au clavier/)).toBeInTheDocument();
  });

  // The canvas itself can't be scanned in jsdom (no 2D context), but the page chrome — toolbar,
  // filters, legend, keyboard-help callout — is real DOM. Type into "Localiser" so the suggestion
  // list (its `aria-label` is part of the FSC-59 fix) actually renders and is scanned too.
  it("has no accessibility violations in the graph view chrome", async () => {
    const { container } = renderGraph();
    await screen.findByText(/institutions affichées sur/);
    await userEvent.type(
      screen.getByLabelText(/Localiser une institution dans le graphe/),
      "Centre",
    );
    await screen.findByRole("button", { name: /Centre national de la recherche scientifique/ });
    expect(await axe(container)).toHaveNoViolations();
  });

  it("has no accessibility violations in the table fallback", async () => {
    const { container } = renderGraph();
    await screen.findByText(/institutions affichées sur/);
    const toggle = screen.getByRole("group", { name: /Mode d’affichage/ });
    await userEvent.click(within(toggle).getByRole("button", { name: /Vue tableau/ }));
    await screen.findByRole("table", { name: /Institutions affichées/ });
    expect(await axe(container)).toHaveNoViolations();
  });
});
