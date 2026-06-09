import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { axe } from "vitest-axe";
import { supabase } from "../../lib/supabase";
import EntityPage from "./EntityPage";

// Mock the Supabase read client. The factory is hoisted, so fixtures live inside it. It models the
// four queries the sheet issues — entity (eq+maybeSingle), edges (or), budget_facts (eq), and the
// counterpart/tutelle name batch (in) — keyed by SIREN so several entities can be exercised.
vi.mock("../../lib/supabase", () => {
  const MESR = "110044013";
  const CNRS = "180089013";
  const ADEME = "130025265";

  const entities: Record<string, Record<string, unknown>> = {
    [MESR]: {
      siren: MESR,
      name: "Ministère de l'Enseignement supérieur et de la Recherche",
      level: "state",
      category: "ministère",
      parent_siren: null,
      provenance: "operateurs_etat",
    },
    [CNRS]: {
      siren: CNRS,
      name: "Centre national de la recherche scientifique",
      level: "state",
      category: "EPST",
      parent_siren: MESR,
      provenance: "operateurs_etat",
    },
    [ADEME]: {
      siren: ADEME,
      name: "ADEME",
      level: "state",
      category: "EPIC",
      parent_siren: null,
      provenance: "operateurs_etat",
    },
  };
  const tutelleEdge = {
    source_siren: MESR,
    target_siren: CNRS,
    type: "tutelle",
    amount_eur: null,
    exercice: null,
    provenance: "operateurs_etat",
  };
  const ademeFundsEdge = {
    source_siren: ADEME,
    target_siren: CNRS,
    type: "funds",
    amount_eur: 1_000_000,
    exercice: 2025,
    provenance: "budget_plf_lfi",
  };
  const allEdges = [tutelleEdge, ademeFundsEdge];
  const budgetBySiren: Record<string, Array<Record<string, unknown>>> = {
    [MESR]: [
      {
        exercice: 2025,
        mission: "MIRES",
        programme: "150",
        amount_ae_eur: 15_217_000_000,
        amount_cp_eur: 15_279_000_000,
        executed: false,
      },
      {
        exercice: 2025,
        mission: "MIRES",
        programme: "172",
        amount_ae_eur: 8_259_807_441,
        amount_cp_eur: 8_701_105_312,
        executed: false,
      },
    ],
  };

  const makeEntities = () => {
    let eqValue = "";
    const builder = {
      select: () => builder,
      eq: (_col: string, value: string) => {
        eqValue = value;
        return builder;
      },
      maybeSingle: () =>
        Promise.resolve(
          eqValue === "000000001"
            ? { data: null, error: { message: "boom" } }
            : { data: entities[eqValue] ?? null, error: null },
        ),
      in: (_col: string, values: string[]) =>
        Promise.resolve({
          data: values
            .map((v) => entities[v])
            .filter(Boolean)
            .map((e) => ({ siren: e.siren, name: e.name })),
          error: null,
        }),
    };
    return builder;
  };
  const makeEdges = () => {
    const builder = {
      select: () => builder,
      // Faithfully models PostgREST .or(source_siren.eq.X,target_siren.eq.X): a row matches when
      // either endpoint is the queried SIREN (exercises target-only entities + direction logic).
      or: (filter: string) => {
        const siren = filter.match(/eq\.(\d{9})/)?.[1] ?? "";
        const data = allEdges.filter((e) => e.source_siren === siren || e.target_siren === siren);
        return Promise.resolve({ data, error: null });
      },
    };
    return builder;
  };
  const makeBudget = () => {
    const builder = {
      select: () => builder,
      eq: (_col: string, value: string) =>
        Promise.resolve({ data: budgetBySiren[value] ?? [], error: null }),
    };
    return builder;
  };

  return {
    supabase: {
      from: vi.fn((table: string) => {
        if (table === "entities") return makeEntities();
        if (table === "edges") return makeEdges();
        return makeBudget();
      }),
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

  it("shows the tutelle as a navigable link resolved by name", async () => {
    renderAt("180089013"); // CNRS → tutelle MESR
    await screen.findByRole("heading", {
      level: 1,
      name: "Centre national de la recherche scientifique",
    });
    // The identity block carries a "Tutelle :" line (distinct from the relationships table, which
    // also links to MESR as this entity's only counterpart).
    const tutelleLine = await screen.findByText(
      (_content, el) => el?.tagName === "LI" && /^Tutelle\s*:/.test(el.textContent ?? ""),
    );
    expect(tutelleLine).toBeInTheDocument();
    // Every link to the ministry resolves it by name and points at its sheet.
    const links = screen.getAllByRole("link", {
      name: "Ministère de l'Enseignement supérieur et de la Recherche",
    });
    expect(links.length).toBeGreaterThanOrEqual(1);
    expect(links.every((l) => l.getAttribute("href") === "/entity/110044013")).toBe(true);
  });

  it("renders the budget facts attributed to a ministry (mission/programme, AE/CP, voté)", async () => {
    renderAt("110044013"); // MESR — owns the seeded MIRES facts
    await screen.findByRole("heading", {
      level: 1,
      name: "Ministère de l'Enseignement supérieur et de la Recherche",
    });
    const budgetTable = await screen.findByRole("table", { name: /Crédits budgétaires/i });
    expect(budgetTable).toBeInTheDocument();
    // Both MIRES programmes and the voted status surface, with a fr-FR–formatted amount.
    expect(screen.getByText("150")).toBeInTheDocument();
    expect(screen.getByText("172")).toBeInTheDocument();
    expect(screen.getAllByText("Voté").length).toBe(2);
    expect(screen.getByText(/15\s217\s000\s000/)).toBeInTheDocument();
  });

  it("shows an empty-state when an entity has no attributed budget facts", async () => {
    renderAt("130025265"); // ADEME — no budget facts in the fixture
    await screen.findByRole("heading", { level: 1, name: "ADEME" });
    expect(await screen.findByText(/Aucun crédit budgétaire/i)).toBeInTheDocument();
    expect(screen.queryByRole("table", { name: /Crédits budgétaires/i })).toBeNull();
  });

  it("renders an error alert when a query fails", async () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    renderAt("000000001"); // sentinel SIREN whose entity query returns an error
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/Impossible de charger cette entité/i);
    spy.mockRestore();
  });

  it("has no accessibility violations", async () => {
    const { container } = renderAt("110044013");
    await screen.findByRole("heading", {
      level: 1,
      name: "Ministère de l'Enseignement supérieur et de la Recherche",
    });
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
