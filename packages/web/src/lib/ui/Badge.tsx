import type { ReactNode } from "react";
import { levelMeta } from "../levels";
import { LevelShape } from "./LevelShape";
import { Warning } from "./icons";

export type BadgeTone = "default" | "blue" | "info" | "success" | "warning" | "error" | "new";

export interface BadgeProps {
  tone?: BadgeTone;
  className?: string;
  children: ReactNode;
}

/** Generic DSFR badge (`.badge`) — a small uppercase status pill. */
export function Badge({ tone = "default", className, children }: BadgeProps) {
  const classes = ["badge", tone !== "default" ? `badge--${tone}` : null, className]
    .filter(Boolean)
    .join(" ");
  return <span className={classes}>{children}</span>;
}

export interface LevelBadgeProps {
  level: string | null | undefined;
  /** Render the "SIREN non résolu" state instead of the level (entity without a resolved SIREN). */
  unresolved?: boolean;
}

/**
 * Administrative-level badge: the level's shape glyph + label, on its categorical hue. Colour is
 * driven by the `LEVELS` SSOT (inline) rather than a CSS class suffix, so it stays correct whatever
 * the DB level key is. Carries a non-colour cue (the glyph) for accessibility.
 */
export function LevelBadge({ level, unresolved = false }: LevelBadgeProps) {
  if (unresolved) {
    return (
      <span className="badge badge--unresolved">
        <Warning style={{ width: 12, height: 12 }} /> SIREN non résolu
      </span>
    );
  }
  const meta = levelMeta(level);
  return (
    <span className="badge badge--niv" style={{ background: meta.color, color: meta.text }}>
      <LevelShape level={level} size={11} color={meta.text} />
      {meta.label}
    </span>
  );
}
