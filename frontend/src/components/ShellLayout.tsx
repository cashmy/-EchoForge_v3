import { ReactNode } from "react";
import { useAppStore } from "../state/useAppStore";

interface ShellLayoutProps {
  children: ReactNode;
}

export const ShellLayout = ({ children }: ShellLayoutProps) => {
  const backendStatus = useAppStore((state) => state.backendStatus);

  return (
    <div className="min-h-screen bg-gradient-to-br from-midnight via-slate to-black text-white">
      <header className="flex items-center justify-between px-8 py-6">
        <h1 className="text-2xl font-semibold tracking-tight">
          EchoForge Console
        </h1>
        <span className="text-sm text-slate-200">
          Backend status: {backendStatus?.status ?? "unknown"}
        </span>
      </header>
      <main className="px-8 pb-12">{children}</main>
    </div>
  );
};
