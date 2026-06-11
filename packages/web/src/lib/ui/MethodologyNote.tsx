import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { Callout } from "./Callout";
import { Info } from "./icons";

export interface MethodologyNoteProps {
  /** Emphasise the State↔local mixed-universe caveat (vs the generic funding-hop one). */
  mixed?: boolean;
  /** Override the body text entirely (e.g. the M57-local note on an entity sheet). */
  children?: ReactNode;
  className?: string;
}

/**
 * Anti-double-counting disclaimer (FSC-42), surfaced wherever a total may double-count or mix
 * accounting universes. Reuses the DSFR info Callout and links to the methodology section on the
 * Données page. Text comes from the `methodology` i18n namespace unless overridden via `children`.
 */
export function MethodologyNote({ mixed = false, children, className }: MethodologyNoteProps) {
  const { t } = useTranslation();
  const body = children ?? t(mixed ? "methodology.mixed" : "methodology.doubleCounting");
  return (
    <Callout tone="info" className={["methodology-note", className].filter(Boolean).join(" ")}>
      <div className="row-center" style={{ gap: 10, alignItems: "flex-start" }}>
        <Info
          style={{ width: 18, height: 18, color: "var(--info)", flex: "none", marginTop: 2 }}
          aria-hidden="true"
        />
        <p className="fr-sm" style={{ margin: 0 }}>
          {body}{" "}
          <Link className="fr-link" to="/sources#double-comptage">
            {t("methodology.seeMore")}
          </Link>
        </p>
      </div>
    </Callout>
  );
}
