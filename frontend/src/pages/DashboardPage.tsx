import { TaxonomyConsole } from "../components/TaxonomyConsole";
import { useAppStore } from "../state/useAppStore";

interface DashboardPageProps {
  showTaxonomyConsole?: boolean;
}

const StatusCard = () => {
  const backendStatus = useAppStore((state) => state.backendStatus);
  const featureFlags = backendStatus?.featureFlags ?? {};
  const taxonomyEnabled = featureFlags.enable_taxonomy_refs_in_capture ?? false;

  return (
    <section className="rounded-3xl border border-slate-800/70 bg-slate-900/70 p-8 shadow-[0_30px_90px_rgba(15,23,42,0.55)]">
      <p className="text-xs uppercase tracking-[0.3em] text-slate-400">
        Runtime Snapshot
      </p>
      <div className="mt-3 flex flex-wrap items-center gap-4 text-3xl font-semibold text-white">
        {backendStatus?.environment ?? "unknown"}
        <span className="text-base font-normal text-slate-400">
          environment
        </span>
      </div>
      <dl className="mt-6 grid gap-4 text-sm text-slate-200 md:grid-cols-3">
        <div className="rounded-2xl border border-slate-800/80 bg-slate-950/40 p-4">
          <dt className="text-xs uppercase tracking-[0.3em] text-slate-500">
            EntryStore
          </dt>
          <dd className="mt-2 text-lg font-semibold text-emerald-200">
            {backendStatus?.entryStore ?? "pending"}
          </dd>
        </div>
        <div className="rounded-2xl border border-slate-800/80 bg-slate-950/40 p-4">
          <dt className="text-xs uppercase tracking-[0.3em] text-slate-500">
            Job Queue
          </dt>
          <dd className="mt-2 text-lg font-semibold text-emerald-200">
            {backendStatus?.jobQueue ?? "pending"}
          </dd>
        </div>
        <div className="rounded-2xl border border-slate-800/80 bg-slate-950/40 p-4">
          <dt className="text-xs uppercase tracking-[0.3em] text-slate-500">
            Taxonomy Capture Flag
          </dt>
          <dd
            className={
              taxonomyEnabled
                ? "mt-2 text-lg font-semibold text-emerald-200"
                : "mt-2 text-lg font-semibold text-amber-200"
            }
          >
            {taxonomyEnabled ? "enabled" : "disabled"}
          </dd>
        </div>
      </dl>
    </section>
  );
};

export const DashboardPage = ({
  showTaxonomyConsole = true,
}: DashboardPageProps) => (
  <div className="space-y-10">
    <StatusCard />
    {showTaxonomyConsole ? (
      <TaxonomyConsole />
    ) : (
      <section className="rounded-3xl border border-slate-800/70 bg-slate-950/60 p-8 text-sm text-slate-200">
        <p className="text-xs uppercase tracking-[0.3em] text-slate-500">
          Taxonomy Console
        </p>
        <p className="mt-2 text-base">
          Hidden for this profile while the capture workflow catches up. Flip
          the `enable_taxonomy_refs_in_capture` feature flag to preview the UI.
        </p>
      </section>
    )}
  </div>
);
