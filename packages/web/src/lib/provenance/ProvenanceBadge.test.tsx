import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { axe } from "vitest-axe";
import { ProvenanceBadge } from "./ProvenanceBadge";

function renderBadge(props: { provenanceId: string; millesime?: number | null }) {
  return render(
    <MemoryRouter>
      <ProvenanceBadge {...props} />
    </MemoryRouter>,
  );
}

describe("ProvenanceBadge", () => {
  it("links to the source entry and shows publisher + licence", () => {
    renderBadge({ provenanceId: "budget_plf_lfi" });
    const link = screen.getByRole("link");
    expect(link).toHaveAttribute("href", "/sources#source-budget_plf_lfi");
    expect(link).toHaveTextContent(/Direction du budget/i);
    expect(link).toHaveTextContent(/Licence Ouverte/i);
  });

  it("includes the millésime when provided", () => {
    renderBadge({ provenanceId: "budget_plf_lfi", millesime: 2025 });
    expect(screen.getByRole("link")).toHaveTextContent(/2025/);
  });

  it("shows an unknown-source label without a link for an unregistered id", () => {
    renderBadge({ provenanceId: "not_a_source" });
    expect(screen.queryByRole("link")).toBeNull();
    expect(screen.getByText(/not_a_source/)).toBeInTheDocument();
  });

  it("has no accessibility violations", async () => {
    const { container } = renderBadge({ provenanceId: "budget_plf_lfi", millesime: 2025 });
    expect(await axe(container)).toHaveNoViolations();
  });
});
