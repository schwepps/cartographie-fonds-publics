import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { Layout } from "./Layout";
import { NotFound } from "./NotFound";
import { featureRouteObjects } from "./routes";

function renderAt(initialPath: string) {
  const router = createMemoryRouter(
    [
      {
        path: "/",
        Component: Layout,
        children: [...featureRouteObjects, { path: "*", Component: NotFound }],
      },
    ],
    { initialEntries: [initialPath] },
  );
  return render(<RouterProvider router={router} />);
}

describe("Layout shell", () => {
  it("renders the Marianne header and the home page at /", async () => {
    renderAt("/");
    expect(screen.getByRole("banner")).toBeInTheDocument();
    expect(screen.getByRole("contentinfo")).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { level: 1, name: /Cartographie des Fonds Publics/i }),
    ).toBeInTheDocument();
  });

  it("renders the registry-driven nav in the design order", () => {
    renderAt("/");
    const nav = screen.getByRole("navigation", { name: /Menu principal/i });
    const labels = within(nav)
      .getAllByRole("link")
      .map((link) => link.getAttribute("aria-label"));
    expect(labels).toEqual([
      "Accueil",
      "Graphe institutionnel",
      "Recherche",
      "Flux de financement",
      "Données & licences",
    ]);
  });

  it("marks the active nav item with aria-current", async () => {
    renderAt("/sources");
    const nav = screen.getByRole("navigation", { name: /Menu principal/i });
    const active = within(nav).getByRole("link", { name: "Données & licences" });
    expect(active).toHaveAttribute("aria-current", "page");
  });

  it("navigates to the search feature from the header tool link", async () => {
    const user = userEvent.setup();
    renderAt("/");
    await user.click(screen.getByRole("link", { name: "Rechercher" }));
    expect(
      await screen.findByRole("heading", { level: 1, name: /Recherche/i }),
    ).toBeInTheDocument();
  });

  it("resolves the Flux nav entry to its placeholder screen (no 404)", async () => {
    const user = userEvent.setup();
    renderAt("/");
    const nav = screen.getByRole("navigation", { name: /Menu principal/i });
    await user.click(within(nav).getByRole("link", { name: "Flux de financement" }));
    expect(
      await screen.findByRole("heading", { level: 1, name: /Flux de financement/i }),
    ).toBeInTheDocument();
  });

  it("shows the 404 page inside the layout for an unknown route", async () => {
    renderAt("/does-not-exist");
    expect(screen.getByRole("banner")).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { level: 1, name: /Page introuvable/i }),
    ).toBeInTheDocument();
  });
});
