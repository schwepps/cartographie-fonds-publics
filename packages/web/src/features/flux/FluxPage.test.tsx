import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import FluxPage from "./FluxPage";

vi.mock("../../lib/supabase", () => {
  const data: Record<string, unknown[]> = {
    entities: [
      {
        siren: "110044013",
        name: "Ministère de la Recherche",
        level: "state",
        category: "ministère",
      },
      { siren: "180089013", name: "CNRS", level: "state", category: "EPST" },
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

const renderFlux = () =>
  render(
    <MemoryRouter>
      <FluxPage />
    </MemoryRouter>,
  );

describe("FluxPage", () => {
  it("renders the Sankey and a synchronized table for the default ministry", async () => {
    renderFlux();
    // The Sankey svg appears once flows load for the default ministry.
    const svg = await screen.findByRole("img", { name: /Diagramme de flux/ });
    expect(svg).toBeInTheDocument();
    const table = await screen.findByRole("table", { name: /Flux de financement/ });
    // financeur → opérateur (funds) + opérateur → titulaire (delegates) = 2 rows.
    expect(within(table).getAllByText(/Financement|Délégation/)).toHaveLength(2);
  });

  it("lets the user pick a financeur ministry", async () => {
    renderFlux();
    await screen.findByRole("table", { name: /Flux de financement/ });
    const select = screen.getByLabelText(/Focaliser sur/);
    expect(
      within(select as HTMLElement).getByRole("option", { name: /Ministère de la Recherche/ }),
    ).toBeInTheDocument();
  });
});
