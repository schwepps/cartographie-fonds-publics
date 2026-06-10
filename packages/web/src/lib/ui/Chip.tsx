import type { ButtonHTMLAttributes } from "react";
import { LevelShape } from "./LevelShape";

export interface ChipProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  /** Selected (filled) vs clickable (tinted) appearance. */
  selected?: boolean;
  /** When set, prepend the level's shape glyph. */
  level?: string | null;
  small?: boolean;
}

/**
 * A pill-shaped, clickable tag/filter (`.tag`) — used for level/category filters that link to the
 * graph or search. Ported from the `design/` export's `Chip`.
 */
export function Chip({
  selected = false,
  level,
  small = false,
  type,
  className,
  children,
  ...rest
}: ChipProps) {
  const classes = [
    "tag",
    selected ? "tag--selected" : "tag--clickable",
    small ? "tag--sm" : null,
    className,
  ]
    .filter(Boolean)
    .join(" ");
  return (
    <button type={type ?? "button"} className={classes} {...rest}>
      {level ? <LevelShape level={level} size={9} color={selected ? "#fff" : undefined} /> : null}
      {children}
    </button>
  );
}
