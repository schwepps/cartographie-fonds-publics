import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { axe } from "vitest-axe";
import { supabase } from "../../lib/supabase";
import EntityPage from "./EntityPage";

// Mock the Supabase read client: the factory is hoisted, so fixtures live inside it.
vi.mock("../../lib/supabase", () => {
  const entity = {
    siren: "130025265",
    name: "ADEME",
    level: "state",
    category: "EPIC",
    provenance: "operateurs_etat",
  };
  const edges = [
    {
      source_siren: "130025265",
      target_siren: "180089013",
      type: "funds",
      amount_eur: 1_000_000,
      exercice: 2025,
      provenance: "budget_plf_lfi",
    },
  ];
  const entitiesBuilder = {
    select: () => entitiesBuilder,
    eq: () => entitiesBuilder,
    maybeSingle: () => Promise.resolve({ data: entity, error: null }),
  };
  const edgesBuilder = {
    select: () => edgesBuilder,
    or: () => Promise.resolve({ data: edges, error: null }),
  };
  return {
    supabase: {
      from: vi.fn((table: string) => (table === "entities" ? entitiesBuilder : edgesBuilder)),
    },
  };
});

beforeEach(() => {
  vi.clearAllMocks();
});

function renderAt(siren: string) {
  return render(
    <MemoryRouter initialEntries={[`/entity/${siren}`]}>
      <Routes>
        <Route path="/entity/:siren" element={<EntityPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("EntityPage", () => {
  it("renders entity identity with an entity-level provenance badge", async () => {
    renderAt("130025265");
    expect(await screen.findByRole("heading", { level: 1, name: "ADEME" })).toBeInTheDocument();
    // The entity itself is attributed to its registry source (no millésime).
    const entityBadge = await screen.findByRole("link", {
      name: "Provenance : Direction du budget, licence Licence Ouverte 2.0",
    });
    expect(entityBadge).toHaveAttribute("href", "/sources#source-operateurs_etat");
  });

  it("renders each edge with a resolved provenance badge (no 'Source inconnue')", async () => {
    renderAt("130025265");
    await screen.findByRole("heading", { level: 1, name: "ADEME" });
    // The figure's provenance links to its source entry and carries the millésime.
    const edgeBadge = await screen.findByRole("link", { name: /millésime 2025/i });
    expect(edgeBadge).toHaveAttribute("href", "/sources#source-budget_plf_lfi");
    expect(screen.queryByText(/Source inconnue/i)).toBeNull();
    // Edges render in the accessible relationships table.
    expect(screen.getByRole("table", { name: /provenance/i })).toBeInTheDocument();
  });

  it("has no accessibility violations", async () => {
    const { container } = renderAt("130025265");
    await screen.findByRole("heading", { level: 1, name: "ADEME" });
    expect(await axe(container)).toHaveNoViolations();
  });

  it("rejects a non-SIREN param without issuing any query (filter-injection guard)", async () => {
    renderAt("1)),or(type.eq.tutelle");
    // Short-circuits to not-found; the malformed value never reaches a PostgREST filter.
    expect(await screen.findByText(/Aucune entité trouvée/i)).toBeInTheDocument();
    expect(screen.queryByRole("heading", { level: 1, name: "ADEME" })).toBeNull();
    expect(supabase.from).not.toHaveBeenCalled();
  });
});
