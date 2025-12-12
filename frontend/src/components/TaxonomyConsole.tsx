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
      status === "ready" && !stale && "bg-emerald-400/15 text-emerald-500",
      status === "ready" && stale && "bg-amber-400/15 text-amber-600",
      status === "loading" && "bg-sky-400/15 text-sky-500",
      status === "error" && "bg-rose-400/15 text-rose-500"
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
        ? "border-emerald-400/40 bg-emerald-400/10 text-emerald-600"
        : "border-rose-400/40 bg-rose-400/10 text-rose-600"
    )}
  >
    <div className="flex items-center justify-between gap-3">
      <span className="font-medium">{record.label}</span>
      {!record.active && (
        <span className="text-xs uppercase tracking-wide text-rose-600">
          inactive
        </span>
      )}
    </div>
    <p className="text-[11px] text-[var(--color-text-muted)]">{record.name}</p>
  </div>
);

const TaxonomyList = ({
  title,
  records,
}: {
  title: string;
  records: TaxonomyRecord[];
}) => (
  <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-raised)] p-4 text-[var(--color-text)]">
    <div className="flex items-center justify-between">
      <h4 className="text-sm font-semibold text-[var(--color-text)]">
        {title}
      </h4>
      <span className="text-xs text-[var(--color-text-muted)]">
        {records.length} items
      </span>
    </div>
    <div className="mt-3 flex flex-wrap gap-3">
      {records.length === 0 ? (
        <p className="text-xs text-[var(--color-text-muted)]">
          No records available.
        </p>
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
    <section className="rounded-3xl border border-[var(--color-border)] bg-[var(--color-surface)] p-8 text-[var(--color-text)] shadow-[0_40px_120px_rgba(2,6,23,0.25)] transition-colors">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.3em] text-[var(--color-text-muted)]">
            Taxonomy Console
          </p>
          <h3 className="mt-1 text-2xl font-semibold text-[var(--color-text)]">
            Classification Inputs
          </h3>
          <p className="text-sm text-[var(--color-text-muted)]">
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
            className="inline-flex items-center gap-2 rounded-full border border-[var(--color-border)] px-4 py-2 text-sm font-semibold text-[var(--color-text)] transition hover:-translate-y-0.5 hover:border-[var(--color-accent)] focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)] disabled:cursor-not-allowed disabled:opacity-60"
          >
            <RefreshCcw className="h-4 w-4" /> Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="mt-6 flex items-center gap-3 rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-700">
          <AlertTriangle className="h-4 w-4" />
          <span>{error}</span>
          <button
            type="button"
            className="ml-auto text-xs font-semibold uppercase tracking-wide text-rose-600"
            onClick={() => loadTaxonomy({ force: true })}
          >
            Retry
          </button>
        </div>
      )}

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <div className="space-y-6">
          <div>
            <label className="text-xs uppercase tracking-[0.3em] text-[var(--color-text-muted)]">
              Entry Type
            </label>
            <div className="mt-2 flex flex-col gap-2 md:flex-row">
              <select
                value={typeSelection}
                onChange={(event) => setTypeSelection(event.target.value)}
                disabled={!canUseTypeSelect}
                className={clsx(
                  "flex-1 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-raised)] px-4 py-3 text-sm text-[var(--color-text)] focus:border-[var(--color-accent)] focus:outline-none",
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
                    ? "border-[var(--color-accent)] bg-[var(--color-accent)]/10 text-[var(--color-accent)]"
                    : "border-[var(--color-border)] text-[var(--color-text)] hover:border-[var(--color-accent)]"
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
                className="mt-3 w-full rounded-2xl border border-[var(--color-accent)]/60 bg-[var(--color-surface-raised)] px-4 py-3 text-sm text-[var(--color-text)] focus:border-[var(--color-accent)] focus:outline-none"
              />
            )}
          </div>

          <div>
            <label className="text-xs uppercase tracking-[0.3em] text-[var(--color-text-muted)]">
              Entry Domain
            </label>
            <div className="mt-2 flex flex-col gap-2 md:flex-row">
              <select
                value={domainSelection}
                onChange={(event) => setDomainSelection(event.target.value)}
                disabled={!canUseDomainSelect}
                className={clsx(
                  "flex-1 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-raised)] px-4 py-3 text-sm text-[var(--color-text)] focus:border-[var(--color-accent)] focus:outline-none",
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
                    ? "border-[var(--color-accent)] bg-[var(--color-accent)]/10 text-[var(--color-accent)]"
                    : "border-[var(--color-border)] text-[var(--color-text)] hover:border-[var(--color-accent)]"
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
                className="mt-3 w-full rounded-2xl border border-[var(--color-accent)]/60 bg-[var(--color-surface-raised)] px-4 py-3 text-sm text-[var(--color-text)] focus:border-[var(--color-accent)] focus:outline-none"
              />
            )}
          </div>

          <div className="flex flex-wrap items-center gap-4 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-raised)] px-4 py-3 text-sm text-[var(--color-text)]">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={includeInactive}
                onChange={handleIncludeInactiveToggle}
                disabled={!featureEnabled}
                className="h-4 w-4 rounded border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-accent)] focus:ring-[var(--color-accent)]"
              />
              Include inactive rows
            </label>
            <span className="text-xs text-[var(--color-text-muted)]">
              Last sync {formatTimestamp(lastFetched)}
            </span>
          </div>
          {!featureEnabled && (
            <div className="flex items-center gap-2 rounded-2xl border border-amber-400/40 bg-amber-400/10 px-4 py-3 text-sm text-amber-700">
              <CloudOff className="h-4 w-4" />
              <span>
                Admin disabled taxonomy refs in capture. Badges stay read-only
                so operators still see stored labels.
              </span>
            </div>
          )}
        </div>

        <div className="rounded-3xl border border-[var(--color-border)] bg-[var(--color-surface-raised)] p-6 text-sm text-[var(--color-text)]">
          <div className="flex items-center gap-3 text-[var(--color-accent)]">
            <Sparkles className="h-5 w-5" />
            <span className="text-xs uppercase tracking-[0.3em]">
              Preview payload
            </span>
          </div>
          <pre className="mt-4 overflow-x-auto rounded-2xl bg-[var(--color-bg)] p-4 text-xs text-[var(--color-text)]">
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
