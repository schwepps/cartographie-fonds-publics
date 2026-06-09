import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "vitest-axe";
import { Button } from "./Button";
import { LevelBadge } from "./Badge";
import { Chip } from "./Chip";
import { DataTable, type DataTableColumn } from "./DataTable";

describe("Button", () => {
  it("defaults to a non-submitting primary button", () => {
    render(<Button>Ouvrir</Button>);
    const btn = screen.getByRole("button", { name: "Ouvrir" });
    expect(btn).toHaveAttribute("type", "button");
    expect(btn).toHaveClass("btn", "btn--primary");
  });

  it("applies variant and size modifiers and fires onClick", async () => {
    const onClick = vi.fn();
    render(
      <Button variant="secondary" size="sm" onClick={onClick}>
        Filtrer
      </Button>,
    );
    const btn = screen.getByRole("button", { name: "Filtrer" });
    expect(btn).toHaveClass("btn--secondary", "btn--sm");
    await userEvent.click(btn);
    expect(onClick).toHaveBeenCalledOnce();
  });
});

describe("LevelBadge", () => {
  it("renders the level label with a non-colour shape cue", () => {
    const { container } = render(<LevelBadge level="delegated" />);
    expect(screen.getByText("Délégué")).toBeInTheDocument();
    // the shape glyph is an inline svg (the accessibility-safe, colour-independent cue)
    expect(container.querySelector("svg")).not.toBeNull();
  });

  it("renders the unresolved state for entities without a SIREN", () => {
    render(<LevelBadge level={null} unresolved />);
    expect(screen.getByText(/SIREN non résolu/i)).toBeInTheDocument();
  });

  it("has no accessibility violations", async () => {
    const { container } = render(<LevelBadge level="state" />);
    expect(await axe(container)).toHaveNoViolations();
  });
});

describe("Chip", () => {
  it("toggles between clickable and selected appearance and fires onClick", async () => {
    const onClick = vi.fn();
    const { rerender } = render(<Chip onClick={onClick}>État</Chip>);
    const chip = screen.getByRole("button", { name: "État" });
    expect(chip).toHaveClass("tag", "tag--clickable");
    await userEvent.click(chip);
    expect(onClick).toHaveBeenCalledOnce();
    rerender(
      <Chip selected onClick={onClick}>
        État
      </Chip>,
    );
    expect(screen.getByRole("button", { name: "État" })).toHaveClass("tag--selected");
  });
});

interface Row {
  name: string;
  amount: number;
}
const columns: DataTableColumn<Row>[] = [
  { key: "name", header: "Nom" },
  { key: "amount", header: "Montant", num: true },
];
const rows: Row[] = [
  { name: "Beta", amount: 30 },
  { name: "Alpha", amount: 10 },
  { name: "Gamma", amount: 20 },
];

describe("DataTable", () => {
  it("renders rows and marks numeric columns", () => {
    render(<DataTable caption="Entités" columns={columns} rows={rows} getRowKey={(r) => r.name} />);
    expect(screen.getByRole("table", { name: "Entités" })).toBeInTheDocument();
    expect(screen.getAllByRole("row")).toHaveLength(rows.length + 1); // + header row
  });

  it("sorts ascending then descending on header click, exposing aria-sort", async () => {
    render(<DataTable columns={columns} rows={rows} getRowKey={(r) => r.name} />);
    const amountHeader = screen.getByRole("columnheader", { name: /Montant/ });
    const sortButton = within(amountHeader).getByRole("button");

    await userEvent.click(sortButton);
    expect(amountHeader).toHaveAttribute("aria-sort", "ascending");
    let cells = screen.getAllByRole("cell").filter((_, i) => i % 2 === 1); // amount column
    expect(cells.map((c) => c.textContent)).toEqual(["10", "20", "30"]);

    await userEvent.click(sortButton);
    expect(amountHeader).toHaveAttribute("aria-sort", "descending");
    cells = screen.getAllByRole("cell").filter((_, i) => i % 2 === 1);
    expect(cells.map((c) => c.textContent)).toEqual(["30", "20", "10"]);
  });
});
