import { Fragment } from "react";
import { Link } from "react-router-dom";

export interface Crumb {
  label: string;
  /** Link target; the last crumb (or any without `to`) renders as plain current text. */
  to?: string;
}

export interface BreadcrumbProps {
  items: Crumb[];
}

/**
 * Breadcrumb (fil d'Ariane, `.breadcrumb`). The final item is marked `aria-current="page"`.
 * Ported from the `design/` export.
 */
export function Breadcrumb({ items }: BreadcrumbProps) {
  return (
    <nav className="breadcrumb" aria-label="Fil d’Ariane">
      {items.map((crumb, index) => {
        const isLast = index === items.length - 1;
        return (
          <Fragment key={`${crumb.label}-${index}`}>
            {index > 0 ? (
              <span className="breadcrumb__sep" aria-hidden="true">
                /
              </span>
            ) : null}
            {crumb.to && !isLast ? (
              <Link to={crumb.to}>{crumb.label}</Link>
            ) : (
              <span aria-current={isLast ? "page" : undefined}>{crumb.label}</span>
            )}
          </Fragment>
        );
      })}
    </nav>
  );
}
