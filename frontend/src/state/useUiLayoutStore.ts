import { create } from "zustand";

type SecondaryPanelView = "entry-detail" | "whisper-settings" | null;
type ThemeMode = "light" | "dark";
type ThemePreference = "system" | ThemeMode;

interface UiLayoutState {
  sidebarCollapsed: boolean;
  mobileNavOpen: boolean;
  secondaryPanelView: SecondaryPanelView;
  themePreference: ThemePreference;
  resolvedTheme: ThemeMode;
  toggleSidebarCollapse: () => void;
  openMobileNav: () => void;
  closeMobileNav: () => void;
  openSecondaryPanel: (view: NonNullable<SecondaryPanelView>) => void;
  closeSecondaryPanel: () => void;
  setResolvedTheme: (theme: ThemeMode) => void;
  cycleThemePreference: () => void;
}

const cycleTheme = (theme: ThemePreference): ThemePreference => {
  if (theme === "system") {
    return "light";
  }
  if (theme === "light") {
    return "dark";
  }
  return "system";
};

export const useUiLayoutStore = create<UiLayoutState>((set) => ({
  sidebarCollapsed: false,
  mobileNavOpen: false,
  secondaryPanelView: null,
  themePreference: "system",
  resolvedTheme: "light",
  toggleSidebarCollapse: () =>
    set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
  openMobileNav: () => set({ mobileNavOpen: true }),
  closeMobileNav: () => set({ mobileNavOpen: false }),
  openSecondaryPanel: (view) => set({ secondaryPanelView: view }),
  closeSecondaryPanel: () => set({ secondaryPanelView: null }),
  setResolvedTheme: (theme) => set({ resolvedTheme: theme }),
  cycleThemePreference: () =>
    set((state) => ({ themePreference: cycleTheme(state.themePreference) })),
}));
