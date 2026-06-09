import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import { supabase } from "../../lib/supabase";
import { useGraphData } from "./useGraphData";

// Mock the Supabase client: a tiny seed network plus a graph_neighbors response introducing one new
// neighbour (a supplier), so the expand path is exercised without a browser/canvas.
vi.mock("../../lib/supabase", () => {
  const nodes = [
    { siren: "110044013", name: "MESR", level: "state", category: "ministère" },
    { siren: "180089013", name: "CNRS", level: "state", category: "EPST" },
  ];
  const edges = [{ source_siren: "110044013", target_siren: "180089013", type: "tutelle" }];
  const neighbourRows = [
    {
      source_siren: "180089013",
      target_siren: "329200521",
      type: "funds",
      amount_eur: 1000,
      hop: 1,
    },
  ];
  const infoRows = [
    { siren: "329200521", name: "Fournisseur", level: "delegated", category: null },
  ];

  const makeEntities = () => {
    const builder = {
      select: () => builder,
      limit: () => Promise.resolve({ data: nodes, error: null }),
      in: () => Promise.resolve({ data: infoRows, error: null }),
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
      rpc: vi.fn(() => Promise.resolve({ data: neighbourRows, error: null })),
    },
  };
});

beforeEach(() => {
  vi.clearAllMocks();
});

describe("useGraphData", () => {
  it("loads the bounded seed network", async () => {
    const { result } = renderHook(() => useGraphData());
    await waitFor(() => expect(result.current.state.status).toBe("ready"));
    if (result.current.state.status !== "ready") throw new Error("expected ready");
    expect(result.current.state.nodes).toHaveLength(2);
    expect(result.current.state.edges).toHaveLength(1);
    expect(result.current.state.truncated).toBe(false);
  });

  it("expands a node via graph_neighbors and merges the new neighbour", async () => {
    const { result } = renderHook(() => useGraphData());
    await waitFor(() => expect(result.current.state.status).toBe("ready"));
    await act(async () => {
      await result.current.expand("180089013");
    });
    expect(supabase.rpc).toHaveBeenCalledWith("graph_neighbors", {
      p_siren: "180089013",
      p_depth: 1,
    });
    if (result.current.state.status !== "ready") throw new Error("expected ready");
    expect(result.current.state.nodes.map((n) => n.siren)).toContain("329200521");
    expect(result.current.state.edges).toHaveLength(2);
  });

  it("ignores a non-SIREN expand argument (RPC trust-boundary guard)", async () => {
    const { result } = renderHook(() => useGraphData());
    await waitFor(() => expect(result.current.state.status).toBe("ready"));
    await act(async () => {
      await result.current.expand("1)),or(type.eq.tutelle");
    });
    expect(supabase.rpc).not.toHaveBeenCalled();
  });

  it("flags expandError (not silent) when graph_neighbors fails", async () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    const { result } = renderHook(() => useGraphData());
    await waitFor(() => expect(result.current.state.status).toBe("ready"));
    vi.mocked(supabase.rpc).mockResolvedValueOnce({
      data: null,
      error: { message: "boom" },
    } as never);
    await act(async () => {
      await result.current.expand("180089013");
    });
    if (result.current.state.status !== "ready") throw new Error("expected ready");
    expect(result.current.state.expandError).toBe(true);
    spy.mockRestore();
  });

  it("surfaces an error state when the initial load fails", async () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    const fromMock = vi.mocked(supabase.from);
    const original = fromMock.getMockImplementation();
    const errResult = { data: null, error: { message: "boom" } };
    // A thenable error builder: chainable AND awaitable, so both the entities(.limit) and
    // edges(awaited .select) queries resolve to an error.
    const errBuilder = {
      select: () => errBuilder,
      limit: () => Promise.resolve(errResult),
      in: () => Promise.resolve(errResult),
      then: (resolve: (value: typeof errResult) => unknown) => resolve(errResult),
    };
    fromMock.mockImplementation(() => errBuilder as never);
    try {
      const { result } = renderHook(() => useGraphData());
      await waitFor(() => expect(result.current.state.status).toBe("error"));
    } finally {
      if (original) fromMock.mockImplementation(original);
      spy.mockRestore();
    }
  });
});
