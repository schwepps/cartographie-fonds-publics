import type { HTMLAttributes } from "react";

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  /** Inner padding (`.card--pad`). */
  pad?: boolean;
  /** Hover elevation for a clickable card (`.card--link`). */
  link?: boolean;
  /** Accent top border in Bleu France (`.card__top-border`). */
  topBorder?: boolean;
}

/** DSFR-style surface container (`.card`). Ported from the `design/` export. */
export function Card({
  pad = false,
  link = false,
  topBorder = false,
  className,
  ...rest
}: CardProps) {
  const classes = [
    "card",
    pad ? "card--pad" : null,
    link ? "card--link" : null,
    topBorder ? "card__top-border" : null,
    className,
  ]
    .filter(Boolean)
    .join(" ");
  return <div className={classes} {...rest} />;
}
