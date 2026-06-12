import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { axe } from "vitest-axe";
import SearchPage from "./SearchPage";

vi.mock("../../lib/supabase", () => {
  const data: Record<string, unknown[]> = {
    entities: [
      {
        siren: "110044013",
        name: "Ministère de la Recherche",
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
      {
        siren: "237500139",
        name: "Région Île-de-France",
        level: "local",
        category: "Région",
        parent_siren: null,
      },
    ],
    edges: [
      {
        source_siren: "110044013",
        target_siren: "180089013",
        type: "funds",
        amount_eur: 2_950_000_000,
      },
    ],
    budget_facts: [
      { entity_siren: "110044013", exercice: 2025, amount_cp_eur: 26_000_000_000, executed: false },
    ],
  };
  const from = (table: string) => {
    const result = { data: data[table] ?? [], error: null, count: 0 };
    const builder = {
      select: () => builder,
      limit: () => builder,
      then: (resolve: (value: typeof result) => unknown) => Promise.resolve(result).then(resolve),
    };
    return builder;
  };
  return { supabase: { from } };
});

const renderSearch = (initial = "/search") =>
  render(
    <MemoryRouter initialEntries={[initial]}>
      <SearchPage />
    </MemoryRouter>,
  );

const resultLinks = () =>
  screen.queryAllByRole("link").filter((a) => a.classList.contains("result"));
// CNRS has a parent, so its full name appears only in its result title (breadcrumb uses acronyms).
const CNRS = /Centre national de la recherche scientifique/;

describe("SearchPage (Recherche)", () => {
  it("lists every institution and links each result to its sheet", async () => {
    renderSearch();
    const cnrs = await screen.findByText(CNRS);
    expect(cnrs.closest("a")).toHaveAttribute("href", "/entity/180089013");
    expect(resultLinks()).toHaveLength(3);
  });

  it("filters by the query (matches the CNRS acronym)", async () => {
    renderSearch();
    await screen.findByText(CNRS);
    await userEvent.type(screen.getByLabelText("Terme de recherche"), "CNRS");
    expect(resultLinks()).toHaveLength(1);
    expect(screen.getByText(CNRS)).toBeInTheDocument();
  });

  it("filters by the niveau facet", async () => {
    renderSearch();
    await screen.findByText(CNRS);
    const filters = screen.getByRole("complementary", { name: "Filtres" });
    // Uncheck "État" → the two state entities disappear, leaving the local one.
    await userEvent.click(within(filters).getByRole("checkbox", { name: /État/ }));
    expect(screen.queryByText(CNRS)).toBeNull();
    expect(resultLinks()).toHaveLength(1);
  });

  it("honours the ?q= seed from the header search", async () => {
    renderSearch("/search?q=Région");
    await screen.findByText(/résultat/);
    expect(resultLinks()).toHaveLength(1);
    expect(screen.queryByText(CNRS)).toBeNull();
  });

  it("has no accessibility violations (results + facets)", async () => {
    const { container } = renderSearch();
    await screen.findByText(CNRS);
    expect(await axe(container)).toHaveNoViolations();
  });
});
