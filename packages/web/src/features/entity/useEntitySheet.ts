import { useEffect, useState } from "react";
import { supabase } from "../../lib/supabase";
import { isSiren } from "../../lib/siren";
import type {
  AttributionRow,
  BudgetFactRow,
  ContractRow,
  EdgeRow,
  EntityRow,
  MentionRow,
  RelatedEntity,
} from "./types";

export type EntitySheetState =
  | { status: "loading" }
  | { status: "error" }
  | {
      status: "ready";
      entity: EntityRow | null;
      edges: EdgeRow[];
      budgetFacts: BudgetFactRow[];
      /** Operators whose tutelle is this entity (parent_siren === siren). */
      children: RelatedEntity[];
      /** DECP contracts where this entity is the acheteur. */
      contracts: ContractRow[];
      /** Legal mandates attached to this entity (FSC-27). */
      attributions: AttributionRow[];
      /** Cour des comptes / CRTC oversight mentions of this entity (FSC-62). */
      mentions: MentionRow[];
      /** SIREN → linked entity (tutelle + relationship counterparts) for readable labels + shapes. */
      related: Map<string, RelatedEntity>;
    };

const EMPTY_READY: EntitySheetState = {
  status: "ready",
  entity: null,
  edges: [],
  budgetFacts: [],
  children: [],
  contracts: [],
  attributions: [],
  mentions: [],
  related: new Map(),
};

/** The entity on the other end of an edge from `siren`'s perspective. */
export function counterpartSiren(edge: EdgeRow, siren: string): string {
  return edge.source_siren === siren ? edge.target_siren : edge.source_siren;
}

/**
 * Loads everything the entity sheet renders: the entity, the edges it participates in (with amounts
 * + provenance), its budget facts (multi-year AE/CP), the operators it supervises, the DECP
 * contracts it bought, and a name/level lookup for every linked SIREN so chips + breadcrumbs read in
 * plain language. All reads go through PostgREST under RLS; the `:siren` param is validated before it
 * reaches a query (filter-injection guard on the `.or(...)` clause).
 */
export function useEntitySheet(siren: string): EntitySheetState {
  const [state, setState] = useState<EntitySheetState>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;

    async function load() {
      if (!isSiren(siren)) {
        setState(EMPTY_READY);
        return;
      }
      setState({ status: "loading" });
      const [entityRes, edgesRes, budgetRes, childrenRes, contractsRes, attribRes, mentionRes] =
        await Promise.all([
          supabase
            .from("entities")
            .select("siren,name,level,category,parent_siren,provenance")
            .eq("siren", siren)
            .maybeSingle(),
          supabase
            .from("edges")
            .select("source_siren,target_siren,type,amount_eur,exercice,provenance")
            .or(`source_siren.eq.${siren},target_siren.eq.${siren}`),
          supabase
            .from("budget_facts")
            .select("exercice,mission,programme,amount_ae_eur,amount_cp_eur,executed")
            .eq("entity_siren", siren),
          supabase.from("entities").select("siren,name,level,category").eq("parent_siren", siren),
          supabase
            .from("contracts")
            .select("acheteur_siren,titulaire_siren,montant_eur,nature,exercice")
            .eq("acheteur_siren", siren),
          supabase
            .from("attributions")
            .select("entity_siren,legal_ref,txt,source_url,provenance")
            .eq("entity_siren", siren),
          supabase
            .from("mentions")
            .select("entity_siren,report_ref,report_date,mention_type,url,note,provenance,license")
            .eq("entity_siren", siren)
            .order("report_date", { ascending: false }),
        ]);

      if (cancelled) return;
      if (
        entityRes.error ||
        edgesRes.error ||
        budgetRes.error ||
        childrenRes.error ||
        contractsRes.error ||
        attribRes.error ||
        mentionRes.error
      ) {
        console.error(
          "Entity sheet load failed",
          entityRes.error ??
            edgesRes.error ??
            budgetRes.error ??
            childrenRes.error ??
            contractsRes.error ??
            attribRes.error ??
            mentionRes.error,
        );
        setState({ status: "error" });
        return;
      }

      const entity = (entityRes.data as EntityRow | null) ?? null;
      const edges = (edgesRes.data as EdgeRow[] | null) ?? [];
      const budgetFacts = (budgetRes.data as BudgetFactRow[] | null) ?? [];
      const children = (childrenRes.data as RelatedEntity[] | null) ?? [];
      const contracts = (contractsRes.data as ContractRow[] | null) ?? [];
      const attributions = (attribRes.data as AttributionRow[] | null) ?? [];
      const mentions = (mentionRes.data as MentionRow[] | null) ?? [];

      // Resolve name + level for every SIREN the sheet links to (tutelle parent + edge counterparts).
      // Children are already full rows; contract titulaires are external suppliers (kept as SIRENs).
      const relatedSirens = new Set<string>();
      if (entity?.parent_siren) relatedSirens.add(entity.parent_siren);
      for (const edge of edges) relatedSirens.add(counterpartSiren(edge, siren));

      const related = new Map<string, RelatedEntity>();
      for (const child of children) related.set(child.siren, child);
      if (relatedSirens.size > 0) {
        const relatedRes = await supabase
          .from("entities")
          .select("siren,name,level,category")
          .in("siren", [...relatedSirens]);
        if (cancelled) return;
        if (relatedRes.error) {
          console.error("Entity related lookup failed", relatedRes.error);
          setState({ status: "error" });
          return;
        }
        for (const row of (relatedRes.data as RelatedEntity[] | null) ?? []) {
          related.set(row.siren, row);
        }
      }

      setState({
        status: "ready",
        entity,
        edges,
        budgetFacts,
        children,
        contracts,
        attributions,
        mentions,
        related,
      });
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [siren]);

  return state;
}
