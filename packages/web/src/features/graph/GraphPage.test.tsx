import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { axe } from "vitest-axe";
import { supabase } from "../../lib/supabase";
import GraphPage from "./GraphPage";

// Sigma needs WebGL, which jsdom lacks; stub it so the page mounts hermetically. The real canvas is
// verified manually/Playwright — here we assert the data layer, the accessible fallback, and links.
vi.mock("sigma", () => ({
  default: class {
    on() {}
    kill() {}
    refresh() {}
  },
}));

vi.mock("../../lib/supabase", () => {
  const nodes = [
    { siren: "110044013", name: "MESR", level: "state", category: "ministère" },
    { siren: "180089013", name: "CNRS", level: "state", category: "EPST" },
  ];
  const edges = [{ source_siren: "110044013", target_siren: "180089013", type: "tutelle" }];
  const makeEntities = () => {
    const builder = {
      select: () => builder,
      limit: () => Promise.resolve({ data: nodes, error: null }),
      in: () => Promise.resolve({ data: [], error: null }),
    };
    return builder;
  };
  const makeEdges = () => {
    const builder = {
      select: () => builder,
      in: () => builder,
      limit: () => Promise.resolve({ data: edges, error: null }),
    };
    return builder;
  };
  return {
    supabase: {
      from: vi.fn((table: string) => (table === "entities" ? makeEntities() : makeEdges())),
      rpc: vi.fn(() => Promise.resolve({ data: [], error: null })),
    },
  };
});

function renderPage() {
  return render(
    <MemoryRouter>
      <GraphPage />
    </MemoryRouter>,
  );
}

describe("GraphPage", () => {
  it("renders accessible node + relationship tables with links through to entity sheets", async () => {
    renderPage();
    const nodeTable = await screen.findByRole("table", { name: /Institutions du graphe/i });
    expect(nodeTable).toBeInTheDocument();
    // Connectivity (edges) is reachable non-visually too, not just the node list.
    expect(screen.getByRole("table", { name: /Relations du graphe/i })).toBeInTheDocument();
    // Each institution links to its sheet (it appears in both the node table and the edge table).
    const cnrsLinks = screen.getAllByRole("link", { name: "CNRS" });
    expect(cnrsLinks.length).toBeGreaterThanOrEqual(1);
    expect(cnrsLinks.every((l) => l.getAttribute("href") === "/entity/180089013")).toBe(true);
    const mesrLinks = screen.getAllByRole("link", { name: "MESR" });
    expect(mesrLinks.every((l) => l.getAttribute("href") === "/entity/110044013")).toBe(true);
  });

  it("has no accessibility violations", async () => {
    const { container } = renderPage();
    await screen.findByRole("table", { name: /Institutions du graphe/i });
    expect(await axe(container)).toHaveNoViolations();
  });

  it("renders an error alert when the load fails", async () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    const fromMock = vi.mocked(supabase.from);
    const original = fromMock.getMockImplementation();
    const errResult = { data: null, error: { message: "boom" } };
    const errBuilder = {
      select: () => errBuilder,
      limit: () => Promise.resolve(errResult),
      then: (resolve: (value: typeof errResult) => unknown) => resolve(errResult),
    };
    fromMock.mockImplementation(() => errBuilder as never);
    try {
      renderPage();
      const alert = await screen.findByRole("alert");
      expect(alert).toHaveTextContent(/Impossible de charger le graphe/i);
    } finally {
      if (original) fromMock.mockImplementation(original);
      spy.mockRestore();
    }
  });
});
