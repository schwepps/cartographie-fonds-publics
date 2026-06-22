import type { ReactNode } from "react";
import { IS_DEMO } from "../config";
import { Info } from "./icons";

export interface ExampleFlagProps {
  children?: ReactNode;
}

/**
 * Marks an illustrative (« exemple ») figure that is not tied to a published source — a key honesty
 * affordance for the money-flow methodology. Renders **only in demo mode** ({@link IS_DEMO}); on
 * real open-data it is a no-op, so it never mislabels live figures as examples.
 */
export function ExampleFlag({ children }: ExampleFlagProps) {
  if (!IS_DEMO) return null;
  return (
    <span className="example-flag">
      <Info style={{ width: 12, height: 12 }} /> {children ?? "Exemple"}
    </span>
  );
}
