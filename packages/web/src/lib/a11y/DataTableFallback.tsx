import type { Key, ReactNode } from "react";

export interface DataTableColumn {
  /** Key used to read the cell value from each row. */
  key: string;
  /** Visible, translated column header. */
  header: string;
}

export interface DataTableFallbackProps {
  /** Accessible table caption describing the data. */
  caption: string;
  columns: DataTableColumn[];
  rows: Array<Record<string, ReactNode>>;
  /** Stable React key per row; defaults to the row index. */
  getRowKey?: (row: Record<string, ReactNode>, index: number) => Key;
}

/**
 * Accessible text/table rendering of a dataset. This is the **required non-visual
 * fallback** that every graphical view (Sigma graph, D3 Sankey) must render with
 * equivalent data, so the information is reachable without sight — see
 * `src/features/README.md`. Plain semantic `<table>` with a `<caption>` and scoped
 * `<th>`s, styled by the design layer's `fr-table` and wrapped in `.table-wrap`.
 */
export function DataTableFallback({
  caption,
  columns,
  rows,
  getRowKey = (_row, index) => index,
}: DataTableFallbackProps) {
  return (
    <div className="table-wrap">
      <table className="fr-table">
        <caption>{caption}</caption>
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={col.key} scope="col">
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={getRowKey(row, index)}>
              {columns.map((col) => (
                <td key={col.key}>{row[col.key]}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
