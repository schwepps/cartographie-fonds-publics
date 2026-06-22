/**
 * Runtime data-mode flag. The app ships two data shapes: the illustrative **demo** seed
 * (`make demo-seed`, fabricated flows for design/preview) and **real** open-data (the live
 * ingestion). The "exemple" honesty badges/qualifiers must show for the demo only — on real data
 * they are misleading. Set `VITE_DATA_MODE=demo` for a demo/preview build; any other value (the
 * default) means real data and the demo markers are hidden.
 */
export const IS_DEMO = import.meta.env.VITE_DATA_MODE === "demo";
