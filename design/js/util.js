/* Shared helpers — plain JS, attached to window for all components. */
(function () {
  const DATA = window.DATA;

  const bySiren = new Map(DATA.entities.map((e) => [e.siren, e]));
  function entity(siren) { return bySiren.get(siren) || null; }
  function nameOf(siren) { const e = bySiren.get(siren); return e ? e.name : siren; }

  // Compact euro formatter: 31,2 Md€ / 254 M€ / 84 925 €
  function euroCompact(v) {
    if (v == null) return "—";
    const abs = Math.abs(v);
    if (abs >= 1e9) return (v / 1e9).toLocaleString("fr-FR", { maximumFractionDigits: 1 }) + " Md€";
    if (abs >= 1e6) return (v / 1e6).toLocaleString("fr-FR", { maximumFractionDigits: abs < 1e7 ? 1 : 0 }) + " M€";
    if (abs >= 1e3) return Math.round(v).toLocaleString("fr-FR") + " €";
    return v.toLocaleString("fr-FR", { maximumFractionDigits: 2 }) + " €";
  }
  function euroFull(v) { return v == null ? "—" : v.toLocaleString("fr-FR", { maximumFractionDigits: 2 }) + " €"; }

  function sourceOf(id) { return DATA.SOURCES.find((s) => s.id === id) || null; }

  // edges touching a siren
  function edgesOf(siren) {
    return DATA.edges.filter((e) => e.source_siren === siren || e.target_siren === siren);
  }
  function childrenOf(siren) {
    return DATA.entities.filter((e) => e.parent_siren === siren);
  }
  function budgetOf(siren) {
    return DATA.budgetFacts.filter((b) => b.entity_siren === siren);
  }
  function contractsOf(siren) {
    return DATA.contracts.filter((c) => c.acheteur_siren === siren || c.titulaire_siren === siren);
  }
  // tutelle chain (breadcrumb): root → … → entity
  function tutelleChain(siren) {
    const chain = [];
    let cur = entity(siren);
    let guard = 0;
    while (cur && guard++ < 10) {
      chain.unshift(cur);
      cur = cur.parent_siren ? entity(cur.parent_siren) : null;
    }
    return chain;
  }

  // sequential colour ramp for amounts (0..1)
  const SEQ = ["#eef3f9", "#cfe0ef", "#9cc1df", "#5e95c7", "#2e6ca8", "#103e6e"];
  function seqColor(t) {
    t = Math.max(0, Math.min(1, t));
    const i = Math.min(SEQ.length - 1, Math.floor(t * (SEQ.length - 1)));
    return SEQ[i];
  }

  function levelMeta(level) { return DATA.LEVELS[level] || { label: level, color: "#929292", shape: "circle" }; }

  // funds flowing OUT of an entity (where its money goes)
  function outflows(siren) {
    return DATA.edges.filter((e) => e.source_siren === siren && (e.type === "funds" || e.type === "delegates") && e.amount_eur);
  }
  function inflows(siren) {
    return DATA.edges.filter((e) => e.target_siren === siren && (e.type === "funds" || e.type === "participation") && e.amount_eur);
  }

  window.U = {
    entity, nameOf, euroCompact, euroFull, sourceOf, edgesOf, childrenOf,
    budgetOf, contractsOf, tutelleChain, seqColor, levelMeta, outflows, inflows, SEQ,
  };
})();
