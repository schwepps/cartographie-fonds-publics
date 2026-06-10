import type { ButtonHTMLAttributes } from "react";

export type ButtonVariant = "primary" | "secondary" | "tertiary" | "tertiary-no-border";
export type ButtonSize = "sm" | "md" | "lg";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  /** Square padding for a glyph-only button. Pair with an explicit `aria-label`. */
  iconOnly?: boolean;
}

/**
 * DSFR-style button (`.btn`). Defaults to `type="button"` so it never submits a form by accident.
 * Ported from the `design/` export's `.btn` component classes.
 */
export function Button({
  variant = "primary",
  size = "md",
  iconOnly = false,
  type,
  className,
  ...rest
}: ButtonProps) {
  const classes = [
    "btn",
    `btn--${variant}`,
    size !== "md" ? `btn--${size}` : null,
    iconOnly ? "btn--icon-only" : null,
    className,
  ]
    .filter(Boolean)
    .join(" ");
  return <button type={type ?? "button"} className={classes} {...rest} />;
}
