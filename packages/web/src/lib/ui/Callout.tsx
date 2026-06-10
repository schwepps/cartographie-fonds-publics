import type { HTMLAttributes } from "react";

export interface CalloutProps extends HTMLAttributes<HTMLDivElement> {
  tone?: "default" | "info" | "warning";
}

/** DSFR callout / notice block (`.callout`) — a highlighted aside. */
export function Callout({ tone = "default", className, ...rest }: CalloutProps) {
  const classes = ["callout", tone !== "default" ? `callout--${tone}` : null, className]
    .filter(Boolean)
    .join(" ");
  return <div className={classes} {...rest} />;
}
