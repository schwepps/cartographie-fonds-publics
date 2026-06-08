import { supabase } from "./lib/supabase";

// Example reads (no API server): data comes straight from Supabase.
//   const { data } = await supabase.from("entities").select("*").eq("level", "state");
//   const { data } = await supabase.rpc("graph_neighbors", { p_siren: "180089013", p_depth: 1 });
export function App() {
  void supabase; // wired; TODO: Sigma.js graph + D3 Sankey, styled with DSFR.
  return (
    <main style={{ fontFamily: "Marianne, sans-serif", padding: 24 }}>
      <h1>Cartographie des Fonds Publics</h1>
      <p>Frontend scaffold — reads Supabase directly (PostgREST + RPC).</p>
    </main>
  );
}
