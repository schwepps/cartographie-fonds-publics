import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { axe } from "vitest-axe";
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

describe("shell accessibility", () => {
  it("exposes a skip link to the main content", async () => {
    renderAt("/");
    await screen.findByRole("heading", { level: 1 });
    const skip = screen.getByRole("link", { name: /Aller au contenu/i });
    expect(skip).toHaveAttribute("href", "#content");
  });

  it("has no automated a11y violations on the home route", async () => {
    const { container } = renderAt("/");
    await screen.findByRole("heading", { level: 1 });
    expect(await axe(container)).toHaveNoViolations();
  });

  it("has no automated a11y violations on the sources route", async () => {
    const { container } = renderAt("/sources");
    await screen.findByRole("heading", { level: 1, name: /Données & licences/i });
    expect(await axe(container)).toHaveNoViolations();
  });
});
