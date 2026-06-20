import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
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
        name: "CNRS - Centre national de la recherche scientifique",
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
  // Search matching is server-side: the rpc() mock (search_entities) filters by name/SIREN, and the
  // page applies only the level/tutelle facets over the returned rows. The from() builder returns
  // table fixtures unfiltered (the empty-query browse default + the budget/ministry lookups).
  const from = (table: string) => {
    const result = { data: data[table] ?? [], error: null, count: (data[table] ?? []).length };
    const builder = {
      select: () => builder,
      limit: () => builder,
      or: () => builder,
      in: () => builder,
      eq: () => builder,
      then: (resolve: (value: typeof result) => unknown) => Promise.resolve(result).then(resolve),
    };
    return builder;
  };
  // The search_entities RPC matches name/SIREN server-side; the mock mirrors that (case-insensitive).
  const rpc = (_name: string, args: { p_query?: string }) => {
    const q = (args?.p_query ?? "").toLowerCase();
    const rows = data.entities as Array<{ name: string; siren: string }>;
    const filtered = rows.filter((e) => e.name.toLowerCase().includes(q) || e.siren.includes(q));
    return Promise.resolve({ data: filtered, error: null });
  };
  return { supabase: { from, rpc } };
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

  it("filters by the query (server-side name match)", async () => {
    renderSearch();
    await screen.findByText(CNRS);
    await userEvent.type(screen.getByLabelText("Terme de recherche"), "CNRS");
    // debounced (250 ms) → search_entities RPC → only CNRS remains.
    await waitFor(() => expect(resultLinks()).toHaveLength(1));
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
    await waitFor(() => expect(resultLinks()).toHaveLength(1));
    expect(screen.queryByText(CNRS)).toBeNull();
  });

  it("has no accessibility violations (results + facets)", async () => {
    const { container } = renderSearch();
    await screen.findByText(CNRS);
    expect(await axe(container)).toHaveNoViolations();
  });
});
