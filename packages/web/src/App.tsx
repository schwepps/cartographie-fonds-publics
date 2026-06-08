import { createBrowserRouter, RouterProvider } from "react-router-dom";
import { Layout } from "./app/Layout";
import { NotFound } from "./app/NotFound";
import { featureRouteObjects } from "./app/routes";

// FROZEN (FSC-22): the app shell. Do NOT add feature imports here — register a
// feature in src/app/routes.tsx and it appears automatically. See src/features/README.md.
const router = createBrowserRouter([
  {
    path: "/",
    Component: Layout,
    children: [...featureRouteObjects, { path: "*", Component: NotFound }],
  },
]);

export function App() {
  return <RouterProvider router={router} />;
}
