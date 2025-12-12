import {
  FilePlus2,
  LayoutDashboard,
  ListTree,
  Settings,
  Shapes,
  X,
} from "lucide-react";
import { NavLink } from "react-router-dom";
import clsx from "clsx";
import { useUiLayoutStore } from "../state/useUiLayoutStore";

const navItems = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/entries", label: "Entries", icon: ListTree },
  { to: "/entries/manual", label: "Add Entry", icon: FilePlus2 },
  { to: "/taxonomy/types", label: "Types & Domains", icon: Shapes },
  { to: "/settings", label: "Settings", icon: Settings },
];

const SidebarNav = ({ onNavigate }: { onNavigate?: () => void }) => (
  <ul className="space-y-1">
    {navItems.map(({ to, label, icon: Icon }) => (
      <li key={to}>
        <NavLink
          to={to}
          onClick={onNavigate}
          className={({ isActive }) =>
            clsx(
              "group flex items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium transition",
              isActive
                ? "bg-[var(--color-surface-raised)] text-[var(--color-text)]"
                : "text-[var(--color-text-muted)] hover:bg-[var(--color-surface-raised)] hover:text-[var(--color-text)]"
            )
          }
          end={to === "/"}
        >
          <Icon className="h-4 w-4" />
          <span>{label}</span>
        </NavLink>
      </li>
    ))}
  </ul>
);

export const Sidebar = () => {
  const collapsed = useUiLayoutStore((state) => state.sidebarCollapsed);
  const mobileNavOpen = useUiLayoutStore((state) => state.mobileNavOpen);
  const closeMobileNav = useUiLayoutStore((state) => state.closeMobileNav);

  return (
    <>
      <aside
        className={clsx(
          "hidden min-h-screen border-r border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-6 text-[var(--color-text)] transition-colors md:flex",
          collapsed ? "md:w-20" : "md:w-64"
        )}
      >
        <div className="flex w-full flex-col gap-8">
          <div className="text-sm font-semibold tracking-wide text-[var(--color-text-muted)]">
            EchoForge
          </div>
          <SidebarNav />
        </div>
      </aside>
      {mobileNavOpen && (
        <div className="fixed inset-0 z-40 flex md:hidden">
          <div className="w-72 border-r border-[var(--color-border)] bg-[var(--color-surface)] p-6 text-[var(--color-text)] shadow-2xl">
            <div className="mb-6 flex items-center justify-between text-[var(--color-text)]">
              <span className="text-base font-semibold">Navigate</span>
              <button
                type="button"
                className="rounded-full border border-[var(--color-border)] bg-[var(--color-surface-raised)] p-1"
                onClick={closeMobileNav}
              >
                <X className="h-4 w-4" />
                <span className="sr-only">Dismiss navigation</span>
              </button>
            </div>
            <SidebarNav onNavigate={closeMobileNav} />
          </div>
          <button
            type="button"
            aria-label="Close navigation overlay"
            className="flex-1 bg-black/50"
            onClick={closeMobileNav}
          />
        </div>
      )}
    </>
  );
};
