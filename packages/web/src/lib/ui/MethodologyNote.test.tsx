import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { MethodologyNote } from "./MethodologyNote";

const renderNote = (ui: React.ReactNode) => render(<MemoryRouter>{ui}</MemoryRouter>);

describe("MethodologyNote", () => {
  it("shows the generic double-counting caveat and deep-links to the methodology anchor", () => {
    renderNote(<MethodologyNote />);
    expect(screen.getByText(/un même euro peut être compté plusieurs fois/)).toBeInTheDocument();
    const link = screen.getByRole("link", { name: /Voir la méthodologie/ });
    expect(link).toHaveAttribute("href", "/sources#double-comptage");
  });

  it("emphasises the mixed-universe caveat when mixed", () => {
    renderNote(<MethodologyNote mixed />);
    expect(screen.getByText(/univers comptables différents/)).toBeInTheDocument();
  });

  it("renders an override message via children (e.g. the M57-local note)", () => {
    renderNote(<MethodologyNote>Comptabilité locale M57.</MethodologyNote>);
    expect(screen.getByText("Comptabilité locale M57.")).toBeInTheDocument();
    // The override replaces the body text but keeps the methodology link.
    expect(screen.queryByText(/un même euro peut être compté/)).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Voir la méthodologie/ })).toBeInTheDocument();
  });
});
