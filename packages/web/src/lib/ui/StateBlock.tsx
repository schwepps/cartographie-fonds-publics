import type { ReactNode } from "react";

export interface StateBlockProps {
  variant?: "default" | "error";
  /** Optional leading glyph (e.g. an icon component). */
  icon?: ReactNode;
  title: string;
  children?: ReactNode;
}

/**
 * Centred loading / empty / error placeholder (`.state-block`) for a panel or page region. Error
 * variant is announced via `role="alert"`. Ported from the `design/` export.
 */
export function StateBlock({ variant = "default", icon, title, children }: StateBlockProps) {
  const classes = ["state-block", variant === "error" ? "state-block--error" : null]
    .filter(Boolean)
    .join(" ");
  return (
    <div className={classes} role={variant === "error" ? "alert" : undefined}>
      {icon ? (
        <span className="state-block__icon" aria-hidden="true">
          {icon}
        </span>
      ) : null}
      <h3 className="fr-h4">{title}</h3>
      {children ? <p>{children}</p> : null}
    </div>
  );
}
