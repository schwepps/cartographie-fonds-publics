import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { axe } from "vitest-axe";
import SourcesPage from "./SourcesPage";

describe("SourcesPage", () => {
  it("lists registry sources with publisher and licence under anchored rows", () => {
    const { container } = render(<SourcesPage />);
    expect(
      screen.getByRole("heading", { level: 1, name: /Données & licences/i }),
    ).toBeInTheDocument();
    // A known source is present with its publisher and an attribution-ready licence.
    expect(screen.getAllByText(/Direction du budget/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Licence Ouverte/i).length).toBeGreaterThan(0);
    // Row anchor lets ProvenanceBadge deep-link to the exact source.
    expect(container.querySelector("#source-budget_plf_lfi")).not.toBeNull();
  });

  it("has no accessibility violations", async () => {
    const { container } = render(<SourcesPage />);
    expect(await axe(container)).toHaveNoViolations();
  });
});
