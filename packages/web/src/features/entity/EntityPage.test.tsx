import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { axe } from "vitest-axe";
import EntityPage from "./EntityPage";

const MESR = "110044013";

// Models the entity-sheet queries: entity (eq+maybeSingle), edges (or), budget (eq), children
// (eq parent_siren), contracts (eq acheteur), related (in). The builder tracks the last filter so a
// table queried several ways (entities) resolves to the right slice.
// The mock factory is hoisted above the module body, so it inlines the SIRENs rather than the outer
// MESR/CNRS consts (which aren't initialised yet at hoist time).
vi.mock("../../lib/supabase", () => {
  const entityRows: Record<string, Record<string, unknown>> = {
    "110044013": {
      siren: "110044013",
      name: "Ministère de l’ESR",
      level: "state",
      category: "ministère",
      parent_siren: null,
      provenance: "operateurs_etat",
    },
    "180089013": {
      siren: "180089013",
      name: "Centre national de la recherche scientifique",
      level: "state",
      category: "EPST",
      parent_siren: "110044013",
      provenance: "operateurs_etat",
    },
    "200053781": {
      siren: "200053781",
      name: "Métropole de Lyon",
      level: "local",
      category: "Métropole",
      parent_siren: null,
      provenance: "finances_locales_ofgl",
    },
    "180035024": {
      siren: "180035024",
      name: "Caisse nationale de l’assurance maladie",
      level: "social",
      category: "Caisse nationale",
      parent_siren: null,
      provenance: "comptes_sociaux",
    },
  };
  const edges = [
    {
      source_siren: "110044013",
      target_siren: "180089013",
      type: "funds",
      amount_eur: 2_950_000_000,
      exercice: 2025,
      provenance: "budget_plf_lfi",
    },
  ];
  // Budget facts keyed by entity_siren (the sheet queries budget_facts.eq(entity_siren, siren)).
  const budgetBySiren: Record<string, Record<string, unknown>[]> = {
    "110044013": [
      {
        exercice: 2025,
        mission: "MIRES",
        programme: "150 — Formations",
        amount_ae_eur: 15_217_000_000,
        amount_cp_eur: 15_279_000_000,
        executed: false,
      },
      {
        exercice: 2024,
        mission: "MIRES",
        programme: "150 — Formations",
        amount_ae_eur: 14_690_000_000,
        amount_cp_eur: 14_710_000_000,
        executed: true,
      },
    ],
    // Local (M57) facts: realised (executed), cash-basis (no AE), agrégat in `programme`.
    "200053781": [
      {
        exercice: 2023,
        mission: null,
        programme: "Dépenses de fonctionnement",
        amount_ae_eur: null,
        amount_cp_eur: 2_300_000_000,
        executed: true,
      },
      {
        exercice: 2023,
        mission: null,
        programme: "Dépenses d’investissement",
        amount_ae_eur: null,
        amount_cp_eur: 900_000_000,
        executed: true,
      },
    ],
    // Social facts: non-LOLF, but NOT M57 — the local wording must not be reused here.
    "180035024": [
      {
        exercice: 2024,
        mission: null,
        programme: "Branche maladie",
        amount_ae_eur: null,
        amount_cp_eur: 240_000_000_000,
        executed: true,
      },
    ],
  };
  const contracts = [
    {
      acheteur_siren: "110044013",
      titulaire_siren: "329200521",
      montant_eur: 1_800_000,
      nature: "marche",
      exercice: 2026,
    },
  ];
  // Attributions keyed by entity_siren (FSC-27): only the ESR ministry has a mandate here.
  const attribBySiren: Record<string, Record<string, unknown>[]> = {
    "110044013": [
      {
        entity_siren: "110044013",
        legal_ref: "Décret n° 2025-1021 du 29 octobre 2025",
        txt: "Compétence enseignement supérieur et recherche.",
        source_url: "https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000052457282",
        provenance: "legifrance_attributions",
      },
    ],
  };
  // Mentions keyed by entity_siren (FSC-62): CNRS has a safe-url rapport + an UNSAFE-url référé.
  const mentionsBySiren: Record<string, Record<string, unknown>[]> = {
    "180089013": [
      {
        entity_siren: "180089013",
        report_ref: "Rapport CNRS 2025",
        report_date: "2025-03-25",
        mention_type: "rapport",
        url: "https://www.ccomptes.fr/fr/publications/cnrs-2025",
        note: "Trésorerie pléthorique.",
        provenance: "cour_des_comptes",
        license: "Licence Ouverte 2.0",
      },
      {
        entity_siren: "180089013",
        report_ref: "Référé CNRS SHS",
        report_date: "2021-04-27",
        mention_type: "recommandation",
        url: "javascript:alert(1)", // unsafe — must render as text, never a link
        note: "Pilotage des SHS.",
        provenance: "cour_des_comptes",
        license: "Licence Ouverte 2.0",
      },
    ],
  };

  const from = (table: string) => {
    const filter: { col?: string; val?: unknown; inVals?: string[] } = {};
    const resolveMany = () => {
      if (table === "edges") return edges;
      if (table === "budget_facts") return budgetBySiren[String(filter.val)] ?? [];
      if (table === "contracts") return contracts;
      if (table === "attributions") return attribBySiren[String(filter.val)] ?? [];
      if (table === "mentions") return mentionsBySiren[String(filter.val)] ?? [];
      if (table === "entities") {
        if (filter.inVals) return filter.inVals.map((s) => entityRows[s]).filter(Boolean);
        if (filter.col === "parent_siren") {
          return Object.values(entityRows).filter((e) => e.parent_siren === filter.val);
        }
      }
      return [];
    };
    const builder = {
      select: () => builder,
      eq: (col: string, val: unknown) => {
        filter.col = col;
        filter.val = val;
        return builder;
      },
      or: () => builder,
      order: () => builder,
      in: (_col: string, vals: string[]) => {
        filter.inVals = vals;
        return builder;
      },
      maybeSingle: () =>
        Promise.resolve({ data: entityRows[String(filter.val)] ?? null, error: null }),
      then: (resolve: (value: { data: unknown[]; error: null }) => unknown) =>
        Promise.resolve({ data: resolveMany(), error: null }).then(resolve),
    };
    return builder;
  };
  return { supabase: { from } };
});

const renderSheet = (siren: string) =>
  render(
    <MemoryRouter initialEntries={[`/entity/${siren}`]}>
      <Routes>
        <Route path="/entity/:siren" element={<EntityPage />} />
      </Routes>
    </MemoryRouter>,
  );

describe("EntityPage (fiche)", () => {
  it("renders the identity header with badges", async () => {
    renderSheet(MESR);
    expect(
      await screen.findByRole("heading", { level: 1, name: /Ministère de l’ESR/ }),
    ).toBeInTheDocument();
    expect(screen.getByText("ministère")).toBeInTheDocument();
  });

  it("shows the voted AE/CP budget figures and the per-programme bars", async () => {
    renderSheet(MESR);
    await screen.findByRole("heading", { level: 1 });
    expect(screen.getByText(/Autorisations d’engagement/)).toBeInTheDocument();
    expect(screen.getByText(/Répartition par programme/)).toBeInTheDocument();
    // The programme appears in the bar + the details table.
    expect(screen.getAllByText(/150 — Formations/).length).toBeGreaterThan(0);
  });

  it("renders a local (M57) sheet with realised expenditure and the methodology note", async () => {
    renderSheet("200053781");
    await screen.findByRole("heading", { level: 1, name: /Métropole de Lyon/ });
    // Local universe: a single realised CP figure (no voté AE column), summing the M57 agrégats.
    expect(screen.getByText(/Dépenses réelles \(CP\)/)).toBeInTheDocument();
    expect(screen.queryByText(/Autorisations d’engagement/)).not.toBeInTheDocument();
    // The accounting-universe disclaimer (FSC-42) appears, linking to the méthodologie anchor.
    expect(screen.getByText(/Comptabilité locale/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Voir la méthodologie/ })).toHaveAttribute(
      "href",
      "/sources#double-comptage",
    );
  });

  it("uses the generic disclaimer (not the M57-local wording) for a social entity", async () => {
    renderSheet("180035024");
    await screen.findByRole("heading", { level: 1, name: /assurance maladie/ });
    // Social budgets are non-LOLF too, but the M57/M14 note is local-specific — it must not leak.
    expect(screen.getByText(/un même euro peut être compté plusieurs fois/)).toBeInTheDocument();
    expect(screen.queryByText(/Comptabilité locale/)).not.toBeInTheDocument();
  });

  it("lists supervised operators as chips linking to their sheets", async () => {
    renderSheet(MESR);
    await screen.findByRole("heading", { level: 1 });
    const card = screen.getByText(/Opérateurs sous tutelle/).closest(".card") as HTMLElement;
    // CNRS appears in both the tutelle card and the funded-operators card; scope to the tutelle one.
    expect(within(card).getByRole("button", { name: /CNRS/ })).toBeInTheDocument();
  });

  it("renders the contracts table (principaux titulaires)", async () => {
    renderSheet(MESR);
    await screen.findByRole("heading", { level: 1 });
    const table = await screen.findByRole("table", { name: /Contrats \(DECP\)/ });
    expect(within(table).getByText(/329200521/)).toBeInTheDocument();
  });

  it("renders attributions with a Légifrance external link (FSC-27, state entity)", async () => {
    renderSheet(MESR);
    await screen.findByRole("heading", { name: /Attributions \/ mandat légal/ });
    const link = screen.getByRole("link", { name: /Décret n° 2025-1021/ });
    expect(link).toHaveAttribute(
      "href",
      "https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000052457282",
    );
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", expect.stringContaining("noopener"));
    // RGAA: a screen-reader warning that the link opens a new window.
    expect(within(link).getByText(/\(nouvelle fenêtre\)/)).toBeInTheDocument();
  });

  it("shows the attributions empty-state for a state entity with none", async () => {
    renderSheet("180089013"); // CNRS: state, no attributions seeded here
    await screen.findByRole("heading", { name: /Attributions \/ mandat légal/ });
    expect(screen.getByText(/Aucune attribution légale renseignée/)).toBeInTheDocument();
  });

  it("hides the attributions section for a non-state entity", async () => {
    renderSheet("200053781"); // Métropole de Lyon (local)
    await screen.findByRole("heading", { level: 1, name: /Métropole de Lyon/ });
    expect(
      screen.queryByRole("heading", { name: /Attributions \/ mandat légal/ }),
    ).not.toBeInTheDocument();
  });

  it("renders Cour des comptes mentions with type tags and only http(s) links (FSC-62)", async () => {
    renderSheet("180089013"); // CNRS has two mentions
    const table = await screen.findByRole("table", { name: /Mentions Cour des comptes/ });
    // Both types render as tags.
    expect(within(table).getByText("Rapport")).toBeInTheDocument();
    expect(within(table).getByText("Recommandation")).toBeInTheDocument();
    // Safe https report renders as an external link…
    const safe = within(table).getByRole("link", { name: /Rapport CNRS 2025/ });
    expect(safe).toHaveAttribute("href", "https://www.ccomptes.fr/fr/publications/cnrs-2025");
    expect(safe).toHaveAttribute("target", "_blank");
    // …but the javascript: url is NEVER an href — the ref renders as plain text.
    expect(within(table).queryByRole("link", { name: /Référé CNRS SHS/ })).not.toBeInTheDocument();
    expect(within(table).getByText("Référé CNRS SHS")).toBeInTheDocument();
  });

  it("shows the Cour des comptes empty-state when there are no mentions", async () => {
    renderSheet(MESR); // no mentions seeded for MESR
    await screen.findByRole("heading", { name: /Cour des comptes/ });
    expect(screen.getByText(/Aucune mention de la Cour des comptes recensée/)).toBeInTheDocument();
  });

  it("has no accessibility violations", async () => {
    const { container } = renderSheet(MESR);
    await screen.findByRole("heading", { level: 1 });
    expect(await axe(container)).toHaveNoViolations();
  });
});
