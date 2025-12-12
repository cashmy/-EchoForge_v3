import { useEffect } from "react";
import { Outlet, useNavigation } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";
import { SecondaryPanel } from "./SecondaryPanel";
import { useUiLayoutStore } from "../state/useUiLayoutStore";

export const AppShell = () => {
  const themePreference = useUiLayoutStore((state) => state.themePreference);
  const setResolvedTheme = useUiLayoutStore((state) => state.setResolvedTheme);
  const navigation = useNavigation();
  const isNavigating = navigation.state !== "idle";

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const computeTheme = (): "light" | "dark" => {
      if (themePreference === "system") {
        return media.matches ? "dark" : "light";
      }
      return themePreference;
    };

    const applyTheme = () => {
      const resolved = computeTheme();
      setResolvedTheme(resolved);
      const root = document.documentElement;
      root.dataset.theme = resolved;
      root.style.colorScheme = resolved;
    };

    applyTheme();

    if (themePreference === "system") {
      media.addEventListener("change", applyTheme);
      return () => media.removeEventListener("change", applyTheme);
    }

    return undefined;
  }, [themePreference, setResolvedTheme]);

  return (
    <div className="min-h-screen bg-[var(--color-bg)] text-[var(--color-text)] transition-colors">
      <div className="flex min-h-screen w-full">
        <Sidebar />
        <div className="flex min-h-screen flex-1 flex-col">
          <TopBar />
          {isNavigating && (
            <div
              className="h-1 w-full animate-pulse bg-[var(--color-accent)]"
              aria-live="polite"
            >
              <span className="sr-only">Navigating…</span>
            </div>
          )}
          <main className="flex-1 px-4 py-6 sm:px-6 lg:px-10" role="main">
            <Outlet />
          </main>
        </div>
        <SecondaryPanel />
      </div>
    </div>
  );
};
