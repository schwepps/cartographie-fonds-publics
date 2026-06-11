import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { axe } from "vitest-axe";
import SourcesPage from "./SourcesPage";

const renderSources = () =>
  render(
    <MemoryRouter>
      <SourcesPage />
    </MemoryRouter>,
  );

describe("SourcesPage (Données & licences)", () => {
  it("lists registry sources with publisher and licence under anchored rows", () => {
    const { container } = renderSources();
    expect(
      screen.getByRole("heading", { level: 1, name: /Données & licences/i }),
    ).toBeInTheDocument();
    expect(screen.getAllByText(/Direction du budget/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Licence Ouverte/i).length).toBeGreaterThan(0);
    // Row anchor lets ProvenanceBadge deep-link to the exact source.
    expect(container.querySelector("#source-budget_plf_lfi")).not.toBeNull();
  });

  it("documents the methodology notes", () => {
    const { container } = renderSources();
    expect(screen.getByText(/Double-comptage/)).toBeInTheDocument();
    expect(screen.getByText(/Accessibilité & code/)).toBeInTheDocument();
    // The double-counting note carries the anchor MethodologyNote deep-links to (FSC-42).
    expect(container.querySelector("#double-comptage")).not.toBeNull();
  });

  it("has no accessibility violations", async () => {
    const { container } = renderSources();
    expect(await axe(container)).toHaveNoViolations();
  });
});
