import { createHashRouter } from "react-router-dom";
import { AppShell } from "../layout/AppShell";
import { DashboardPage } from "../pages/DashboardPage";
import { EntriesListPage } from "../pages/EntriesListPage";
import { EntryDetailPage } from "../pages/EntryDetailPage";
import { ManualEntryPage } from "../pages/ManualEntryPage";
import { SettingsPage } from "../pages/SettingsPage";
import {
  TaxonomyDomainsPage,
  TaxonomyTypesPage,
} from "../pages/TaxonomyTypesPage";
import { NotFoundPage } from "../pages/NotFoundPage";
import { RouteErrorPage } from "../pages/RouteErrorPage";

export const appRouter = createHashRouter([
  {
    path: "/",
    element: <AppShell />,
    errorElement: <RouteErrorPage />,
    children: [
      { index: true, element: <DashboardPage /> },
      { path: "entries", element: <EntriesListPage /> },
      { path: "entries/manual", element: <ManualEntryPage /> },
      { path: "entries/:entryId", element: <EntryDetailPage /> },
      { path: "taxonomy/types", element: <TaxonomyTypesPage /> },
      { path: "taxonomy/domains", element: <TaxonomyDomainsPage /> },
      { path: "settings", element: <SettingsPage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
]);
