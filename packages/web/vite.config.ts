import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import yaml from "js-yaml";
import type { Plugin } from "vite";
import { defineConfig } from "vitest/config";

const REGISTRY_PATH = fileURLToPath(
  new URL("../../data/registry/sources-registry.yaml", import.meta.url),
);
const VIRTUAL_ID = "virtual:sources-registry";
const RESOLVED_VIRTUAL_ID = `\0${VIRTUAL_ID}`;

/**
 * Exposes the source registry (single source of truth, `data/registry/sources-registry.yaml`)
 * to the web build as `import registry from "virtual:sources-registry"`. The YAML is parsed at
 * config time so nothing is hardcoded in the frontend and an annual re-slug needs no code change.
 * Works in dev, `vite build`, and vitest (vitest reuses this config).
 */
function sourcesRegistryPlugin(): Plugin {
  return {
    name: "sources-registry",
    resolveId(id) {
      if (id === VIRTUAL_ID) return RESOLVED_VIRTUAL_ID;
    },
    load(id) {
      if (id !== RESOLVED_VIRTUAL_ID) return;
      // JSON schema: keep `updated: 2026-06-08` a plain string (the default schema would
      // resolve it to a Date and serialize it as an ISO timestamp).
      const raw = yaml.load(readFileSync(REGISTRY_PATH, "utf8"), {
        schema: yaml.JSON_SCHEMA,
      }) as Record<string, unknown>;
      // Fail loud on registry drift (golden rule #3, mirroring the registry's own
      // `drift_policy: fail_loud`): the web's only registry reader must reject a malformed
      // shape at build time, not ship undefined values the .d.ts promises are present.
      const fail = (msg: string): never => {
        throw new Error(`virtual:sources-registry — ${msg} in ${REGISTRY_PATH}`);
      };
      if (typeof raw.updated !== "string") fail("missing string `updated`");
      if (typeof raw.license_default !== "string") fail("missing string `license_default`");
      if (!Array.isArray(raw.sources)) fail("expected a `sources` array");
      const required = ["id", "layer", "publisher", "description", "cadence"] as const;
      const sources = (raw.sources as Record<string, unknown>[]).map((s, i) => {
        for (const key of required) {
          if (typeof s?.[key] !== "string") fail(`source[${i}] missing string \`${key}\``);
        }
        return {
          id: s.id,
          layer: s.layer,
          publisher: s.publisher,
          description: s.description,
          license: typeof s.license === "string" ? s.license : null,
          cadence: s.cadence,
        };
      });
      const registry = {
        updated: raw.updated,
        licenseDefault: raw.license_default,
        sources,
      };
      return `export default ${JSON.stringify(registry)};`;
    },
    configureServer(server) {
      // Pick up registry edits during dev without restarting the server.
      server.watcher.add(REGISTRY_PATH);
    },
    handleHotUpdate(ctx) {
      if (ctx.file === REGISTRY_PATH) {
        const mod = ctx.server.moduleGraph.getModuleById(RESOLVED_VIRTUAL_ID);
        if (mod) return [mod];
      }
    },
  };
}

export default defineConfig({
  plugins: [react(), sourcesRegistryPlugin()],
  server: { port: 5173 },
  test: {
    environment: "jsdom",
    globals: false,
    setupFiles: ["./src/test/setup.ts"],
  },
});
