import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { axe } from "vitest-axe";
import FluxPage from "./FluxPage";

// The Flux view surfaces real `delegates` flows: the top_delegators RPC seeds the buyer selector,
// then the focused buyer's scoped delegates edges drive the Sankey (financeur→opérateur funds have
// no open-data source yet).
vi.mock("../../lib/supabase", () => {
  const entities = [
    { siren: "180089013", name: "CNRS", level: "state" },
    { siren: "329200521", name: "Fournisseur Labo SA", level: "delegated" },
  ];
  const edges = [
    {
      source_siren: "180089013",
      target_siren: "329200521",
      type: "delegates",
      amount_eur: 1_800_000,
      exercice: 2026,
    },
  ];
  const delegators = [
    { siren: "180089013", name: "CNRS", level: "state", total_eur: 1_800_000, contracts: 1 },
  ];
  const from = (table: string) => {
    const result = {
      data: table === "edges" ? edges : table === "entities" ? entities : [],
      error: null,
    };
    const builder = {
      select: () => builder,
      limit: () => builder,
      eq: () => builder,
      in: () => builder,
      order: () => builder,
      then: (resolve: (value: typeof result) => unknown) => Promise.resolve(result).then(resolve),
    };
    return builder;
  };
  const rpc = (name: string) =>
    Promise.resolve({ data: name === "top_delegators" ? delegators : [], error: null });
  return { supabase: { from, rpc } };
});

const renderFlux = (initialEntry = "/flux") =>
  render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <FluxPage />
    </MemoryRouter>,
  );

describe("FluxPage", () => {
  it("renders the Sankey + synchronized table of the default buyer's delegations", async () => {
    renderFlux();
    const svg = await screen.findByRole("img", { name: /Diagramme de flux/ });
    expect(svg).toBeInTheDocument();
    const table = await screen.findByRole("table", { name: /Flux de financement/ });
    // The buyer's one delegation (opérateur → titulaire) = 1 row.
    expect(within(table).getAllByText(/Délégation/)).toHaveLength(1);
  });

  it("lets the user pick a public buyer from the top-delegators selector", async () => {
    renderFlux();
    await screen.findByRole("table", { name: /Flux de financement/ });
    const select = screen.getByLabelText(/Focaliser sur/);
    expect(within(select as HTMLElement).getByRole("option", { name: /CNRS/ })).toBeInTheDocument();
  });

  it("keeps the selector synced when a ?focus= deep link resolves to no name", async () => {
    // Unknown buyer: absent from both the top_delegators list and entities, so its name never
    // resolves. The current focus must still appear as a (SIREN-labelled) option so the controlled
    // <select value={root}> is not left pointing at a missing option.
    renderFlux("/flux?focus=999999999");
    const select = (await screen.findByLabelText(/Focaliser sur/)) as HTMLSelectElement;
    // The label/select render during loading too, so wait for the focus option to appear before
    // asserting on the value — otherwise the check can race the async data load.
    const focusOption = await within(select).findByRole("option", { name: "999999999" });
    expect(focusOption).toBeInTheDocument();
    expect(select.value).toBe("999999999");
  });

  it("has no accessibility violations (Sankey + table fallback)", async () => {
    const { container } = renderFlux();
    await screen.findByRole("img", { name: /Diagramme de flux/ });
    expect(await axe(container)).toHaveNoViolations();
  });
});
