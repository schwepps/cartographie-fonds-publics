import type { ReactNode } from "react";
import { Info } from "./icons";

export interface ExampleFlagProps {
  children?: ReactNode;
}

/**
 * Marks an illustrative (« exemple ») figure that is not tied to a published source — a key honesty
 * affordance for the money-flow methodology. Ported from the `design/` export.
 */
export function ExampleFlag({ children }: ExampleFlagProps) {
  return (
    <span className="example-flag">
      <Info style={{ width: 12, height: 12 }} /> {children ?? "Exemple"}
    </span>
  );
}
