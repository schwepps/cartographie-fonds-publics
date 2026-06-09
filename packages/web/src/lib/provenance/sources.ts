import registry from "virtual:sources-registry";

/**
 * A data source, projected from the registry (`data/registry/sources-registry.yaml`)
 * with the licence resolved against the registry default. This is the single source
 * of truth the provenance UI reads — nothing about sources is hardcoded in the web.
 */
export interface Source {
  /** Stable registry id; also the `edges.provenance` value and the sources-page anchor. */
  id: string;
  /** Logical layer (institutions, funding_state, delegated…). */
  layer: string;
  /** Producing organisation — the name to attribute under Licence Ouverte. */
  publisher: string;
  description: string;
  /** Resolved licence: the source's own, else the registry default. */
  licence: string;
  /** Update frequency (annual, monthly, daily, continuous…). */
  cadence: string;
}

/** Registry default licence, applied when a source omits its own. */
export const licenseDefault = registry.licenseDefault;

/** ISO date the registry was last updated — a coarse, registry-level "as-of". */
export const registryUpdatedAt = registry.updated;

function toSource(s: (typeof registry.sources)[number]): Source {
  return {
    id: s.id,
    layer: s.layer,
    publisher: s.publisher,
    description: s.description,
    licence: s.license ?? licenseDefault,
    cadence: s.cadence,
  };
}

const byId = new Map<string, Source>(registry.sources.map((s) => [s.id, toSource(s)]));

/** Every source, in registry order. */
export function allSources(): Source[] {
  return registry.sources.map(toSource);
}

/** The source for a provenance id, or `undefined` if the id is not in the registry. */
export function getSource(id: string): Source | undefined {
  return byId.get(id);
}

/** Resolved licence for a provenance id; falls back to the registry default for unknown ids. */
export function licenceOf(id: string): string {
  return byId.get(id)?.licence ?? licenseDefault;
}
