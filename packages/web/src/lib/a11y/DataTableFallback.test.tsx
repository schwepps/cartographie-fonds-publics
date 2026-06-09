import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { axe } from "vitest-axe";
import { DataTableFallback } from "./DataTableFallback";

const columns = [
  { key: "name", header: "Nom" },
  { key: "amount", header: "Montant" },
];
const rows = [
  { name: "ADEME", amount: "1 000 €" },
  { name: "CNRS", amount: "2 000 €" },
];

describe("DataTableFallback", () => {
  it("renders an accessible table with caption, headers and cells", () => {
    render(<DataTableFallback caption="Relations" columns={columns} rows={rows} />);
    const table = screen.getByRole("table", { name: "Relations" });
    expect(table).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Nom" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "ADEME" })).toBeInTheDocument();
    expect(screen.getAllByRole("row")).toHaveLength(3); // header + 2 data rows
  });

  it("has no accessibility violations", async () => {
    const { container } = render(
      <DataTableFallback caption="Relations" columns={columns} rows={rows} />,
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
