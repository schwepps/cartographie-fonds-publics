/**
 * Type contract for the `virtual:sources-registry` module produced by the
 * `sources-registry` Vite plugin (see `vite.config.ts`). `tsc --noEmit` does not
 * run Vite, so this declaration is what type-checks consumers of the module.
 */
declare module "virtual:sources-registry" {
  /** One source entry, projected from `data/registry/sources-registry.yaml`. */
  export interface RegistrySource {
    id: string;
    layer: string;
    publisher: string;
    description: string;
    /** Per-source licence; `null` falls back to the registry's `licenseDefault`. */
    license: string | null;
    cadence: string;
  }

  export interface SourcesRegistry {
    /** ISO date the registry was last updated. */
    updated: string;
    /** Default licence applied when a source omits its own. */
    licenseDefault: string;
    sources: RegistrySource[];
  }

  const registry: SourcesRegistry;
  export default registry;
}
