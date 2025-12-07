import { useAppStore } from "../state/useAppStore";

export const DashboardPage = () => {
  const backendStatus = useAppStore((state) => state.backendStatus);

  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900/80 p-8 shadow-2xl">
      <h2 className="text-xl font-semibold">System Overview</h2>
      <p className="mt-4 text-sm text-slate-300">
        EntryStore connection: {backendStatus?.entryStore ?? "pending"}
      </p>
      <p className="text-sm text-slate-300">
        Job queue: {backendStatus?.jobQueue ?? "pending"}
      </p>
    </section>
  );
};
