import type { ReactNode } from "react";

export interface FigureProps {
  /** Headline value (e.g. a formatted amount or count). */
  value: ReactNode;
  label: ReactNode;
  /** Optional provenance line (e.g. a `ProvenanceBadge`). */
  provenance?: ReactNode;
  /** Accent top border in Bleu France. */
  topBorder?: boolean;
}

/**
 * A headline figure card (`.figure`) — a big tabular-number value, a label, and an optional
 * provenance line. Used on the landing overview. Ported from the design reference.
 */
export function Figure({ value, label, provenance, topBorder = true }: FigureProps) {
  return (
    <div
      className="figure"
      style={topBorder ? undefined : { borderTop: "1px solid var(--border-default)" }}
    >
      <div className="figure__value tnum">{value}</div>
      <div className="figure__label">{label}</div>
      {provenance != null ? <div className="figure__prov">{provenance}</div> : null}
    </div>
  );
}
