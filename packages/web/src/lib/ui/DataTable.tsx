import type { ReactNode } from "react";
import { useMemo, useState } from "react";
import { ArrowDown, ArrowUp } from "./icons";

export interface DataTableColumn<Row> {
  /** Stable column id; also the default row accessor key. */
  key: string;
  header: ReactNode;
  /** Right-align + tabular numerals for numeric columns. */
  num?: boolean;
  /** Set false to disable sorting on this column (default: sortable). */
  sortable?: boolean;
  /** Cell renderer; defaults to the raw `row[key]` value. */
  render?: (row: Row) => ReactNode;
  /** Value used for comparison when sorting; defaults to `row[key]`. */
  sortValue?: (row: Row) => string | number;
}

export interface DataTableProps<Row> {
  caption?: ReactNode;
  columns: DataTableColumn<Row>[];
  rows: Row[];
  getRowKey: (row: Row) => string;
  /** Optional DOM id per `<tr>` (e.g. for deep-link anchors like `#source-<id>`). */
  getRowId?: (row: Row) => string;
}

type SortState = { key: string; dir: "asc" | "desc" } | null;
type AriaSort = "none" | "ascending" | "descending";

function cellValue<Row>(row: Row, key: string): unknown {
  return (row as Record<string, unknown>)[key];
}

/**
 * Generic, accessible, sortable table (`.fr-table`). Clicking a header toggles asc → desc → unsorted;
 * the active column carries `aria-sort` for assistive tech. Sorting is stable and locale-aware (fr).
 * Ported from the `design/` export (`components.jsx`).
 */
export function DataTable<Row>({
  caption,
  columns,
  rows,
  getRowKey,
  getRowId,
}: DataTableProps<Row>) {
  const [sort, setSort] = useState<SortState>(null);

  const sorted = useMemo(() => {
    if (!sort) return rows;
    const col = columns.find((c) => c.key === sort.key);
    if (!col) return rows;
    const copy = [...rows].sort((a, b) => {
      const av = col.sortValue ? col.sortValue(a) : cellValue(a, sort.key);
      const bv = col.sortValue ? col.sortValue(b) : cellValue(b, sort.key);
      if (typeof av === "number" && typeof bv === "number") return av - bv;
      return String(av).localeCompare(String(bv), "fr");
    });
    return sort.dir === "desc" ? copy.reverse() : copy;
  }, [rows, sort, columns]);

  function toggle(key: string) {
    setSort((current) => {
      if (current && current.key === key) {
        return current.dir === "asc" ? { key, dir: "desc" } : null;
      }
      return { key, dir: "asc" };
    });
  }

  return (
    <div className="table-wrap">
      <table className="fr-table">
        {caption ? <caption>{caption}</caption> : null}
        <thead>
          <tr>
            {columns.map((col) => {
              const active = sort?.key === col.key;
              const ariaSort: AriaSort = active
                ? sort?.dir === "asc"
                  ? "ascending"
                  : "descending"
                : "none";
              return (
                <th key={col.key} className={col.num ? "num" : undefined} aria-sort={ariaSort}>
                  {col.sortable === false ? (
                    col.header
                  ) : (
                    <button type="button" className="sort" onClick={() => toggle(col.key)}>
                      {col.header}
                      {active ? (
                        sort?.dir === "asc" ? (
                          <ArrowUp style={{ width: 13, height: 13 }} />
                        ) : (
                          <ArrowDown style={{ width: 13, height: 13 }} />
                        )
                      ) : null}
                    </button>
                  )}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row) => (
            <tr key={getRowKey(row)} id={getRowId?.(row)}>
              {columns.map((col) => (
                <td key={col.key} className={col.num ? "num" : undefined}>
                  {col.render ? col.render(row) : (cellValue(row, col.key) as ReactNode)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
