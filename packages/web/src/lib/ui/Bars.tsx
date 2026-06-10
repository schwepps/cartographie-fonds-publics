import type { ReactNode } from "react";

export interface BarItem {
  label: ReactNode;
  /** Numeric magnitude driving the fill width. */
  value: number;
  /** Right-aligned amount text (already formatted). */
  amount?: ReactNode;
  /** Fill colour (defaults to a sequential-ramp blue). */
  color?: string;
}

export interface BarsProps {
  items: BarItem[];
  /** Reference max for the fill scale (defaults to the largest item). */
  max?: number;
}

/**
 * Horizontal magnitude bars (`.bars` / `.bar-row`) — used for budget programmes and "où va son
 * argent" outflows. Ported from the design reference.
 */
export function Bars({ items, max }: BarsProps) {
  const peak = max ?? Math.max(1, ...items.map((i) => i.value));
  return (
    <div className="bars">
      {items.map((item, index) => (
        <div className="bar-row" key={index}>
          <div className="bar-row__head">
            <span>{item.label}</span>
            {item.amount != null ? <span className="tnum">{item.amount}</span> : null}
          </div>
          <div className="bar-row__track">
            <div
              className="bar-row__fill"
              style={{
                width: `${Math.max(2, (item.value / peak) * 100)}%`,
                background: item.color ?? "var(--seq-5)",
              }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
