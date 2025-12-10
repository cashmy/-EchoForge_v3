import { useMemo, useState } from "react";
import clsx from "clsx";
import { AlertTriangle, CloudOff, RefreshCcw, Sparkles } from "lucide-react";
import { useTaxonomyStore } from "../state/useTaxonomyStore";
import type { TaxonomyRecord } from "../api/taxonomy";

const formatTimestamp = (timestamp?: number) => {
  if (!timestamp) {
    return "never";
  }
  return new Date(timestamp).toLocaleTimeString();
};

const StatusPill = ({ status, stale }: { status: string; stale?: string }) => (
  <div
    className={clsx(
      "inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold",
      status === "ready" && !stale && "bg-emerald-500/10 text-emerald-200",
      status === "ready" && stale && "bg-amber-500/10 text-amber-200",
      status === "loading" && "bg-cyan-500/10 text-cyan-200",
      status === "error" && "bg-rose-500/10 text-rose-200"
    )}
  >
    <span className="h-2 w-2 rounded-full bg-current" />
    {stale ? `${status} • ${stale}` : status}
  </div>
);

const TaxonomyBadge = ({ record }: { record: TaxonomyRecord }) => (
  <div
    className={clsx(
      "rounded-xl border px-3 py-2 text-sm transition",
      record.active
        ? "border-emerald-500/20 bg-emerald-500/5 text-emerald-100"
        : "border-rose-500/30 bg-rose-500/5 text-rose-100"
    )}
  >
    <div className="flex items-center justify-between gap-3">
      <span className="font-medium">{record.label}</span>
      {!record.active && (
        <span className="text-xs uppercase tracking-wide text-rose-200">
          inactive
        </span>
      )}
    </div>
    <p className="text-[11px] text-slate-300/80">{record.name}</p>
  </div>
);

const TaxonomyList = ({
  title,
  records,
}: {
  title: string;
  records: TaxonomyRecord[];
}) => (
  <div className="rounded-2xl border border-slate-800/70 bg-slate-950/40 p-4">
    <div className="flex items-center justify-between">
      <h4 className="text-sm font-semibold text-slate-100">{title}</h4>
      <span className="text-xs text-slate-400">{records.length} items</span>
    </div>
    <div className="mt-3 flex flex-wrap gap-3">
      {records.length === 0 ? (
        <p className="text-xs text-slate-500">No records available.</p>
      ) : (
        records
          .slice(0, 8)
          .map((record) => (
            <TaxonomyBadge key={`${title}-${record.id}`} record={record} />
          ))
      )}
    </div>
  </div>
);

export const TaxonomyConsole = () => {
  const {
    types,
    domains,
    status,
    error,
    includeInactive,
    staleReason,
    lastFetched,
    featureEnabled,
    loadTaxonomy,
    setIncludeInactive,
  } = useTaxonomyStore((state) => ({
    types: state.types,
    domains: state.domains,
    status: state.status,
    error: state.error,
    includeInactive: state.includeInactive,
    staleReason: state.staleReason,
    lastFetched: state.lastFetched,
    featureEnabled: state.featureEnabled,
    loadTaxonomy: state.loadTaxonomy,
    setIncludeInactive: state.setIncludeInactive,
  }));

  const [typeSelection, setTypeSelection] = useState<string>("");
  const [domainSelection, setDomainSelection] = useState<string>("");
  const [customTypeLabel, setCustomTypeLabel] = useState<string>("");
  const [customDomainLabel, setCustomDomainLabel] = useState<string>("");
  const [useCustomType, setUseCustomType] = useState(false);
  const [useCustomDomain, setUseCustomDomain] = useState(false);

  const selectedType = useMemo(
    () => types.find((record) => record.id === typeSelection),
    [typeSelection, types]
  );
  const selectedDomain = useMemo(
    () => domains.find((record) => record.id === domainSelection),
    [domainSelection, domains]
  );

  const canUseTypeSelect =
    featureEnabled && (status === "ready" || types.length > 0);
  const canUseDomainSelect =
    featureEnabled && (status === "ready" || domains.length > 0);

  const handleRefresh = () => loadTaxonomy({ force: true });

  const handleIncludeInactiveToggle = () => {
    const nextValue = !includeInactive;
    setIncludeInactive(nextValue);
    loadTaxonomy({ force: true, includeInactive: nextValue });
  };

  return (
    <section className="rounded-3xl border border-slate-800/70 bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 p-8 text-slate-100 shadow-[0_40px_120px_rgba(15,23,42,0.65)]">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.3em] text-emerald-300">
            Taxonomy Console
          </p>
          <h3 className="mt-1 text-2xl font-semibold text-white">
            Classification Inputs
          </h3>
          <p className="text-sm text-slate-300/80">
            Hydrates EF-07 /types & /domains for dropdowns, custom labels, and
            audit-friendly badges.
          </p>
        </div>
        <div className="flex flex-col items-end gap-3 lg:flex-row">
          <StatusPill status={status} stale={staleReason} />
          <button
            type="button"
            onClick={handleRefresh}
            disabled={status === "loading" || !featureEnabled}
            className="inline-flex items-center gap-2 rounded-full border border-emerald-400/40 px-4 py-2 text-sm font-semibold text-emerald-100 transition hover:-translate-y-0.5 hover:border-emerald-300/80 focus:outline-none focus:ring-2 focus:ring-emerald-500 disabled:cursor-not-allowed disabled:border-slate-600 disabled:text-slate-500"
          >
            <RefreshCcw className="h-4 w-4" /> Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="mt-6 flex items-center gap-3 rounded-2xl border border-rose-600/40 bg-rose-600/10 px-4 py-3 text-sm text-rose-100">
          <AlertTriangle className="h-4 w-4" />
          <span>{error}</span>
          <button
            type="button"
            className="ml-auto text-xs font-semibold uppercase tracking-wide"
            onClick={() => loadTaxonomy({ force: true })}
          >
            Retry
          </button>
        </div>
      )}

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <div className="space-y-6">
          <div>
            <label className="text-xs uppercase tracking-[0.3em] text-slate-400">
              Entry Type
            </label>
            <div className="mt-2 flex flex-col gap-2 md:flex-row">
              <select
                value={typeSelection}
                onChange={(event) => setTypeSelection(event.target.value)}
                disabled={!canUseTypeSelect}
                className={clsx(
                  "flex-1 rounded-2xl border border-slate-700 bg-slate-950 px-4 py-3 text-sm text-white focus:border-emerald-400 focus:outline-none",
                  !canUseTypeSelect && "cursor-not-allowed opacity-60"
                )}
              >
                <option value="">Select a type…</option>
                {types.map((record) => (
                  <option key={record.id} value={record.id}>
                    {record.label}
                    {!record.active ? " (inactive)" : ""}
                  </option>
                ))}
              </select>
              <button
                type="button"
                onClick={() => setUseCustomType((value) => !value)}
                disabled={!featureEnabled}
                className={clsx(
                  "rounded-2xl border px-4 py-3 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-60",
                  useCustomType
                    ? "border-emerald-400/60 bg-emerald-500/10 text-emerald-100"
                    : "border-slate-700 text-slate-200 hover:border-emerald-400/40"
                )}
              >
                Custom label
              </button>
            </div>
            {useCustomType && (
              <input
                value={customTypeLabel}
                onChange={(event) => setCustomTypeLabel(event.target.value)}
                placeholder="Project Brief, Risk Review, …"
                className="mt-3 w-full rounded-2xl border border-emerald-400/40 bg-slate-950 px-4 py-3 text-sm text-white focus:border-emerald-400 focus:outline-none"
              />
            )}
          </div>

          <div>
            <label className="text-xs uppercase tracking-[0.3em] text-slate-400">
              Entry Domain
            </label>
            <div className="mt-2 flex flex-col gap-2 md:flex-row">
              <select
                value={domainSelection}
                onChange={(event) => setDomainSelection(event.target.value)}
                disabled={!canUseDomainSelect}
                className={clsx(
                  "flex-1 rounded-2xl border border-slate-700 bg-slate-950 px-4 py-3 text-sm text-white focus:border-emerald-400 focus:outline-none",
                  !canUseDomainSelect && "cursor-not-allowed opacity-60"
                )}
              >
                <option value="">Select a domain…</option>
                {domains.map((record) => (
                  <option key={record.id} value={record.id}>
                    {record.label}
                    {!record.active ? " (inactive)" : ""}
                  </option>
                ))}
              </select>
              <button
                type="button"
                onClick={() => setUseCustomDomain((value) => !value)}
                disabled={!featureEnabled}
                className={clsx(
                  "rounded-2xl border px-4 py-3 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-60",
                  useCustomDomain
                    ? "border-emerald-400/60 bg-emerald-500/10 text-emerald-100"
                    : "border-slate-700 text-slate-200 hover:border-emerald-400/40"
                )}
              >
                Custom label
              </button>
            </div>
            {useCustomDomain && (
              <input
                value={customDomainLabel}
                onChange={(event) => setCustomDomainLabel(event.target.value)}
                placeholder="Product Ops, Partner Success, …"
                className="mt-3 w-full rounded-2xl border border-emerald-400/40 bg-slate-950 px-4 py-3 text-sm text-white focus:border-emerald-400 focus:outline-none"
              />
            )}
          </div>

          <div className="flex flex-wrap items-center gap-4 rounded-2xl border border-slate-800/60 bg-slate-950/40 px-4 py-3 text-sm">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={includeInactive}
                onChange={handleIncludeInactiveToggle}
                disabled={!featureEnabled}
                className="h-4 w-4 rounded border-slate-600 bg-slate-900 text-emerald-400 focus:ring-emerald-500"
              />
              Include inactive rows
            </label>
            <span className="text-xs text-slate-400">
              Last sync {formatTimestamp(lastFetched)}
            </span>
          </div>
          {!featureEnabled && (
            <div className="flex items-center gap-2 rounded-2xl border border-amber-400/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
              <CloudOff className="h-4 w-4" />
              <span>
                Admin disabled taxonomy refs in capture. Badges stay read-only
                so operators still see stored labels.
              </span>
            </div>
          )}
        </div>

        <div className="rounded-3xl border border-emerald-500/30 bg-emerald-500/5 p-6 text-sm text-emerald-50">
          <div className="flex items-center gap-3 text-emerald-200">
            <Sparkles className="h-5 w-5" />
            <span className="text-xs uppercase tracking-[0.3em]">
              Preview payload
            </span>
          </div>
          <pre className="mt-4 overflow-x-auto rounded-2xl bg-slate-950/60 p-4 text-xs text-emerald-100">
            {JSON.stringify(
              {
                taxonomy: {
                  type: useCustomType
                    ? {
                        id: null,
                        label: customTypeLabel || null,
                      }
                    : selectedType
                    ? {
                        id: selectedType.id,
                        label: selectedType.label,
                        active: selectedType.active,
                      }
                    : null,
                  domain: useCustomDomain
                    ? {
                        id: null,
                        label: customDomainLabel || null,
                      }
                    : selectedDomain
                    ? {
                        id: selectedDomain.id,
                        label: selectedDomain.label,
                        active: selectedDomain.active,
                      }
                    : null,
                },
              },
              null,
              2
            )}
          </pre>
        </div>
      </div>

      <div className="mt-8 grid gap-6 lg:grid-cols-2">
        <TaxonomyList title="Types" records={types} />
        <TaxonomyList title="Domains" records={domains} />
      </div>
    </section>
  );
};
