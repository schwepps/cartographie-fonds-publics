import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
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
  it("renders the DSFR header and the home page at /", async () => {
    renderAt("/");
    expect(screen.getByRole("banner")).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: /Cartographie des Fonds Publics/i,
      }),
    ).toBeInTheDocument();
  });

  it("navigates to the search feature from the header search bar", async () => {
    const user = userEvent.setup();
    renderAt("/");
    // DSFR's Header renders the search input twice (desktop + mobile modal); the
    // first is the visible desktop one.
    const [input] = await screen.findAllByRole("searchbox");
    await user.type(input, "ademe");
    await user.keyboard("{Enter}");
    expect(await screen.findByText(/Résultats pour/i)).toBeInTheDocument();
    expect(screen.getByText(/ademe/i)).toBeInTheDocument();
  });

  it("shows the 404 page inside the layout for an unknown route", async () => {
    renderAt("/does-not-exist");
    expect(screen.getByRole("banner")).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { level: 1, name: /Page introuvable/i }),
    ).toBeInTheDocument();
  });
});
