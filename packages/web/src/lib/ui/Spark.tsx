export interface SparkPoint {
  /** Axis label (e.g. the exercice year). */
  label: string;
  value: number;
  /** Highlight as the current/latest bar. */
  current?: boolean;
}

export interface SparkProps {
  points: SparkPoint[];
  /** Accessible description of what the trend shows. */
  ariaLabel: string;
}

/**
 * Tiny multi-year trend bar chart (`.spark`). Decorative bars carry per-bar titles; the whole chart
 * is labelled for assistive tech (pair it with the figures/table that carry the exact numbers).
 */
export function Spark({ points, ariaLabel }: SparkProps) {
  const peak = Math.max(1, ...points.map((p) => p.value));
  return (
    <div className="spark" role="img" aria-label={ariaLabel}>
      {points.map((point) => (
        <div
          key={point.label}
          className={`spark__bar${point.current ? " is-current" : ""}`}
          style={{ height: `${Math.max(6, (point.value / peak) * 100)}%` }}
          title={point.label}
        />
      ))}
    </div>
  );
}
