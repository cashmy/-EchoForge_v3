import { Menu, PanelLeftOpen, SunMoon } from "lucide-react";
import { useUiLayoutStore } from "../state/useUiLayoutStore";
import { useAppStore } from "../state/useAppStore";

const ThemeBadge = () => {
  const theme = useUiLayoutStore((state) => state.themePreference);
  const resolvedTheme = useUiLayoutStore((state) => state.resolvedTheme);
  const cycleTheme = useUiLayoutStore((state) => state.cycleThemePreference);
  const label =
    theme === "system" ? `system (${resolvedTheme})` : theme ?? "system";

  return (
    <button
      type="button"
      className="inline-flex items-center gap-2 rounded-full border border-[var(--color-border)] bg-[var(--color-surface-raised)] px-3 py-1 text-xs font-semibold text-[var(--color-text)]"
      onClick={cycleTheme}
    >
      <SunMoon className="h-3.5 w-3.5" />
      <span className="uppercase tracking-widest">{label}</span>
    </button>
  );
};

const BackendStatusPill = () => {
  const backendStatus = useAppStore((state) => state.backendStatus);
  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-[var(--color-border)] bg-[var(--color-surface-raised)] px-3 py-1 text-xs text-[var(--color-text-muted)]">
      <span
        className="h-2 w-2 rounded-full bg-[var(--color-success)]"
        aria-hidden
      />
      {backendStatus?.status ?? "checking backend"}
    </span>
  );
};

export const TopBar = () => {
  const toggleSidebarCollapse = useUiLayoutStore(
    (state) => state.toggleSidebarCollapse
  );
  const openMobileNav = useUiLayoutStore((state) => state.openMobileNav);

  return (
    <header className="flex h-16 w-full items-center justify-between border-b border-[var(--color-border)] bg-[var(--color-surface)] px-4 shadow-lg shadow-black/10 transition-colors sm:px-6">
      <div className="flex items-center gap-3 text-[var(--color-text)]">
        <button
          type="button"
          className="rounded-full border border-[var(--color-border)] bg-[var(--color-surface-raised)] p-2 text-[var(--color-text)] md:hidden"
          onClick={openMobileNav}
          aria-label="Open navigation"
        >
          <Menu className="h-4 w-4" />
        </button>
        <button
          type="button"
          className="hidden rounded-full border border-[var(--color-border)] bg-[var(--color-surface-raised)] p-2 text-[var(--color-text)] md:inline-flex"
          aria-label="Collapse sidebar"
          onClick={toggleSidebarCollapse}
        >
          <PanelLeftOpen className="h-4 w-4" />
        </button>
        <div>
          <p className="text-xs uppercase tracking-[0.3em] text-[var(--color-text-muted)]">
            EchoForge v3
          </p>
          <p className="text-base font-semibold text-[var(--color-text)]">
            Desktop Workspace
          </p>
        </div>
      </div>
      <div className="flex items-center gap-4">
        <BackendStatusPill />
        <ThemeBadge />
      </div>
    </header>
  );
};
