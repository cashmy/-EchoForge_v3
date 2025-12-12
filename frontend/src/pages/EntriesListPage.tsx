import { FormEvent, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useEntriesSearch } from "../hooks/useEntriesSearch";
import type { EntryListItem } from "../api/entries";
import { useTaxonomyStore } from "../state/useTaxonomyStore";
import { useUiLayoutStore } from "../state/useUiLayoutStore";

const PAGE_SIZE = 20;

const PIPELINE_STATUS_VALUES = [
  "captured",
  "ingested",
  "queued_for_transcription",
  "transcription_in_progress",
  "transcription_complete",
  "transcription_failed",
  "queued_for_extraction",
  "extraction_in_progress",
  "extraction_complete",
  "extraction_failed",
  "queued_for_normalization",
  "normalization_in_progress",
  "normalization_complete",
  "normalization_failed",
  "queued_for_semantics",
  "semantic_in_progress",
  "semantic_complete",
  "semantic_failed",
];

const pipelineStatusOptions = PIPELINE_STATUS_VALUES.map((value) => ({
  value,
  label: formatLabel(value),
}));

const SOURCE_CHANNEL_OPTIONS = [
  "manual_text",
  "watch_folder_audio",
  "watch_folder_document",
  "watch_folder_semantic",
  "api_ingest",
].map((value) => ({
  value,
  label: formatLabel(value),
}));

function formatLabel(value: string) {
  return value
    .replace(/_/g, " ")
    .replace(/\b(\w)/g, (match) => match.toUpperCase())
    .trim();
}

function formatDateTime(value?: string | null) {
  return value ? new Date(value).toLocaleString() : "—";
}

function formatSummary(text?: string | null) {
  if (!text) {
    return "No summary available yet.";
  }
  if (text.length <= 220) {
    return text;
  }
  return `${text.slice(0, 220)}…`;
}

const toStartOfDayIso = (value?: string) =>
  value ? new Date(`${value}T00:00:00Z`).toISOString() : undefined;

const toEndOfDayIso = (value?: string) =>
  value ? new Date(`${value}T23:59:59.999Z`).toISOString() : undefined;

const formatDateForFilter = (value: string) =>
  new Date(`${value}T00:00:00Z`).toLocaleDateString();

const EntriesLoadingState = () => (
  <div className="space-y-3">
    {[1, 2, 3].map((item) => (
      <div
        key={item}
        className="h-20 animate-pulse rounded-2xl border border-dashed border-[var(--color-border)] bg-[var(--color-surface)]"
      />
    ))}
  </div>
);

const EntriesErrorState = ({ onRetry }: { onRetry: () => void }) => (
  <div className="flex flex-wrap items-center gap-3 rounded-2xl border border-rose-400/40 bg-rose-400/10 px-4 py-3 text-sm text-rose-600">
    <span>Unable to load entries right now.</span>
    <button
      type="button"
      onClick={onRetry}
      className="rounded-full border border-rose-500 px-3 py-1 text-xs font-semibold uppercase tracking-widest"
    >
      Retry
    </button>
  </div>
);

const EntriesEmptyState = () => (
  <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-8 text-center text-sm text-[var(--color-text-muted)]">
    No entries match the current search. Adjust the filters or try a different
    query.
  </div>
);

const EntriesTable = ({ items }: { items: EntryListItem[] }) => (
  <div className="overflow-x-auto rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)]">
    <table className="min-w-full divide-y divide-[var(--color-border)] text-sm">
      <thead className="bg-[var(--color-surface-raised)] text-xs uppercase tracking-[0.25em] text-[var(--color-text-muted)]">
        <tr>
          <th className="px-4 py-3 text-left">Entry</th>
          <th className="px-4 py-3 text-left">Pipeline</th>
          <th className="px-4 py-3 text-left">Cognitive</th>
          <th className="px-4 py-3 text-right">Last Updated</th>
          <th className="px-4 py-3 text-right">Actions</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-[var(--color-border)] text-[var(--color-text)]">
        {items.map((entry) => (
          <tr key={entry.entry_id} className="align-top">
            <td className="px-4 py-3">
              <Link
                to={`/entries/${entry.entry_id}`}
                className="font-semibold text-[var(--color-accent)] hover:underline"
              >
                {entry.display_title ?? entry.entry_id}
              </Link>
              <p className="mt-1 text-xs text-[var(--color-text-muted)]">
                {entry.type_label ?? "Unlabeled"} • {entry.domain_label ?? "—"}
              </p>
              <p className="mt-2 text-sm text-[var(--color-text-muted)]">
                {formatSummary(entry.summary_preview ?? entry.summary)}
              </p>
            </td>
            <td className="px-4 py-3 text-sm">
              <p className="font-semibold">
                {formatLabel(entry.pipeline_status)}
              </p>
              <p className="text-xs text-[var(--color-text-muted)]">
                {entry.ingest_state
                  ? formatLabel(entry.ingest_state)
                  : "pending"}
              </p>
            </td>
            <td className="px-4 py-3 text-sm">
              <p className="font-semibold">
                {entry.cognitive_status
                  ? formatLabel(entry.cognitive_status)
                  : "pending"}
              </p>
              <p className="text-xs text-[var(--color-text-muted)]">
                {formatLabel(entry.source_channel)}
              </p>
            </td>
            <td className="px-4 py-3 text-right text-sm">
              {formatDateTime(entry.updated_at)}
            </td>
            <td className="px-4 py-3 text-right">
              <Link
                to={`/entries/${entry.entry_id}`}
                className="inline-flex rounded-full border border-[var(--color-border)] px-4 py-2 text-xs font-semibold uppercase tracking-[0.3em] text-[var(--color-accent)] hover:border-[var(--color-accent)]"
              >
                Open Detail
              </Link>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  </div>
);

const AppliedFilters = ({
  filters,
}: {
  filters: { label: string; value: string }[];
}) => {
  if (filters.length === 0) {
    return null;
  }
  return (
    <div className="flex flex-wrap gap-2 text-xs text-[var(--color-text-muted)]">
      {filters.map((filter) => (
        <span
          key={`${filter.label}-${filter.value}`}
          className="rounded-full border border-[var(--color-border)] bg-[var(--color-surface-raised)] px-3 py-1"
        >
          <strong className="mr-1 uppercase tracking-[0.2em]">
            {filter.label}:
          </strong>
          {filter.value}
        </span>
      ))}
    </div>
  );
};

const PaginationControls = ({
  page,
  totalPages,
  disablePrev,
  disableNext,
  onPrev,
  onNext,
  start,
  end,
  totalItems,
}: {
  page: number;
  totalPages: number;
  disablePrev: boolean;
  disableNext: boolean;
  onPrev: () => void;
  onNext: () => void;
  start: number;
  end: number;
  totalItems: number;
}) => (
  <div className="flex flex-wrap items-center justify-between gap-4 text-sm">
    <p className="text-[var(--color-text-muted)]">
      Showing {totalItems === 0 ? 0 : start}-{end} of{" "}
      {totalItems.toLocaleString()}
    </p>
    <div className="flex items-center gap-2">
      <button
        type="button"
        onClick={onPrev}
        disabled={disablePrev}
        className="rounded-full border border-[var(--color-border)] px-4 py-2 text-xs font-semibold uppercase tracking-[0.3em] disabled:opacity-50"
      >
        Prev
      </button>
      <span className="text-xs uppercase tracking-[0.3em] text-[var(--color-text-muted)]">
        Page {page} / {Math.max(totalPages, 1)}
      </span>
      <button
        type="button"
        onClick={onNext}
        disabled={disableNext}
        className="rounded-full border border-[var(--color-border)] px-4 py-2 text-xs font-semibold uppercase tracking-[0.3em] disabled:opacity-50"
      >
        Next
      </button>
    </div>
  </div>
);

export const EntriesListPage = () => {
  const navigate = useNavigate();
  const openSecondaryPanel = useUiLayoutStore(
    (state) => state.openSecondaryPanel
  );
  const types = useTaxonomyStore((state) => state.types);
  const domains = useTaxonomyStore((state) => state.domains);
  const taxonomyStatus = useTaxonomyStore((state) => state.status);

  const [searchInput, setSearchInput] = useState("");
  const [activeQuery, setActiveQuery] = useState<string | undefined>();
  const [typeFilter, setTypeFilter] = useState<string | undefined>();
  const [domainFilter, setDomainFilter] = useState<string | undefined>();
  const [pipelineFilter, setPipelineFilter] = useState<string | undefined>();
  const [sourceChannelFilter, setSourceChannelFilter] = useState<
    string | undefined
  >();
  const [createdFromInput, setCreatedFromInput] = useState("");
  const [createdToInput, setCreatedToInput] = useState("");
  const [includeArchived, setIncludeArchived] = useState(false);
  const [page, setPage] = useState(1);

  const searchParams = useMemo(
    () => ({
      q: activeQuery,
      typeIds: typeFilter ? [typeFilter] : undefined,
      domainIds: domainFilter ? [domainFilter] : undefined,
      pipelineStatuses: pipelineFilter ? [pipelineFilter] : undefined,
      sourceChannels: sourceChannelFilter ? [sourceChannelFilter] : undefined,
      createdFrom: toStartOfDayIso(createdFromInput || undefined),
      createdTo: toEndOfDayIso(createdToInput || undefined),
      includeArchived,
      page,
      pageSize: PAGE_SIZE,
      sortBy: "updated_at",
      sortDir: "desc" as const,
    }),
    [
      activeQuery,
      typeFilter,
      domainFilter,
      pipelineFilter,
      sourceChannelFilter,
      createdFromInput,
      createdToInput,
      includeArchived,
      page,
    ]
  );

  const { data, isLoading, isFetching, isError, refetch } =
    useEntriesSearch(searchParams);

  const pagination = data?.pagination;
  const items = data?.items ?? [];
  const totalItems = pagination?.total_items ?? 0;
  const currentPage = pagination?.page ?? page;
  const totalPages = pagination?.total_pages ?? 1;
  const pageSize = pagination?.page_size ?? PAGE_SIZE;
  const start = totalItems === 0 ? 0 : (currentPage - 1) * pageSize + 1;
  const end =
    totalItems === 0 ? 0 : Math.min(currentPage * pageSize, totalItems);

  const handleSearchSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = searchInput.trim();
    setActiveQuery(trimmed || undefined);
    setPage(1);
  };

  const handleReset = () => {
    setSearchInput("");
    setActiveQuery(undefined);
    setTypeFilter(undefined);
    setDomainFilter(undefined);
    setPipelineFilter(undefined);
    setSourceChannelFilter(undefined);
    setCreatedFromInput("");
    setCreatedToInput("");
    setIncludeArchived(false);
    setPage(1);
  };

  const activeFilters = useMemo(() => {
    const resolveLabel = (
      records: { id: string; label: string }[],
      id?: string
    ) => records.find((record) => record.id === id)?.label ?? id;

    const filters = [] as { label: string; value: string }[];
    if (activeQuery) {
      filters.push({ label: "Search", value: activeQuery });
    }
    if (typeFilter) {
      filters.push({
        label: "Type",
        value: resolveLabel(types, typeFilter) ?? typeFilter,
      });
    }
    if (domainFilter) {
      filters.push({
        label: "Domain",
        value: resolveLabel(domains, domainFilter) ?? domainFilter,
      });
    }
    if (pipelineFilter) {
      filters.push({ label: "Pipeline", value: formatLabel(pipelineFilter) });
    }
    if (sourceChannelFilter) {
      filters.push({
        label: "Source",
        value: formatLabel(sourceChannelFilter),
      });
    }
    if (createdFromInput || createdToInput) {
      const fromLabel = createdFromInput
        ? formatDateForFilter(createdFromInput)
        : undefined;
      const toLabel = createdToInput
        ? formatDateForFilter(createdToInput)
        : undefined;
      const value =
        fromLabel && toLabel
          ? `${fromLabel} – ${toLabel}`
          : fromLabel || toLabel || "";
      filters.push({ label: "Created", value });
    }
    if (includeArchived) {
      filters.push({ label: "Archived", value: "Included" });
    }
    return filters;
  }, [
    activeQuery,
    typeFilter,
    domainFilter,
    pipelineFilter,
    sourceChannelFilter,
    createdFromInput,
    createdToInput,
    includeArchived,
    types,
    domains,
  ]);

  const disablePrev = currentPage <= 1 || isFetching;
  const disableNext = currentPage >= totalPages || isFetching;

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.3em] text-[var(--color-text-muted)]">
            Entries Workspace
          </p>
          <h1 className="text-2xl font-semibold text-[var(--color-text)]">
            Entries
          </h1>
          <p className="mt-2 text-sm text-[var(--color-text-muted)]">
            Live data powered by `/api/entries`. Apply filters to focus on the
            work that matters most right now.
          </p>
        </div>
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-raised)] px-4 py-2 text-sm font-semibold text-[var(--color-text)]"
            onClick={() => openSecondaryPanel("whisper-settings")}
          >
            Whisper Status
          </button>
          <button
            type="button"
            className="rounded-lg border border-[var(--color-accent)] bg-[var(--color-accent)]/10 px-4 py-2 text-sm font-semibold text-[var(--color-accent)]"
            onClick={() => navigate("/entries/manual")}
          >
            Add Entry
          </button>
        </div>
      </header>

      <section className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6">
        <form className="space-y-4" onSubmit={handleSearchSubmit}>
          <div className="flex flex-col gap-2">
            <label className="text-xs uppercase tracking-[0.3em] text-[var(--color-text-muted)]">
              Search Entries
            </label>
            <input
              type="search"
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
              placeholder="Search titles, summaries, or tags…"
              className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-raised)] px-4 py-2 text-sm text-[var(--color-text)] focus:border-[var(--color-accent)] focus:outline-none"
            />
          </div>
          <div className="grid gap-4 md:grid-cols-4">
            <div className="flex flex-col gap-2">
              <label className="text-xs uppercase tracking-[0.3em] text-[var(--color-text-muted)]">
                Type
              </label>
              <select
                value={typeFilter ?? ""}
                onChange={(event) => {
                  setTypeFilter(event.target.value || undefined);
                  setPage(1);
                }}
                className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-raised)] px-3 py-2 text-sm"
              >
                <option value="">All types</option>
                {types.map((record) => (
                  <option key={record.id} value={record.id}>
                    {record.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-2">
              <label className="text-xs uppercase tracking-[0.3em] text-[var(--color-text-muted)]">
                Domain
              </label>
              <select
                value={domainFilter ?? ""}
                onChange={(event) => {
                  setDomainFilter(event.target.value || undefined);
                  setPage(1);
                }}
                className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-raised)] px-3 py-2 text-sm"
              >
                <option value="">All domains</option>
                {domains.map((record) => (
                  <option key={record.id} value={record.id}>
                    {record.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-2">
              <label className="text-xs uppercase tracking-[0.3em] text-[var(--color-text-muted)]">
                Pipeline Status
              </label>
              <select
                value={pipelineFilter ?? ""}
                onChange={(event) => {
                  setPipelineFilter(event.target.value || undefined);
                  setPage(1);
                }}
                className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-raised)] px-3 py-2 text-sm"
              >
                <option value="">All statuses</option>
                {pipelineStatusOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-2">
              <label className="text-xs uppercase tracking-[0.3em] text-[var(--color-text-muted)]">
                Source Channel
              </label>
              <select
                value={sourceChannelFilter ?? ""}
                onChange={(event) => {
                  setSourceChannelFilter(event.target.value || undefined);
                  setPage(1);
                }}
                className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-raised)] px-3 py-2 text-sm"
              >
                <option value="">All channels</option>
                {SOURCE_CHANNEL_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <div className="flex flex-col gap-2">
              <label className="text-xs uppercase tracking-[0.3em] text-[var(--color-text-muted)]">
                Created From
              </label>
              <input
                type="date"
                value={createdFromInput}
                onChange={(event) => {
                  setCreatedFromInput(event.target.value);
                  setPage(1);
                }}
                className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-raised)] px-3 py-2 text-sm"
              />
            </div>
            <div className="flex flex-col gap-2">
              <label className="text-xs uppercase tracking-[0.3em] text-[var(--color-text-muted)]">
                Created To
              </label>
              <input
                type="date"
                value={createdToInput}
                onChange={(event) => {
                  setCreatedToInput(event.target.value);
                  setPage(1);
                }}
                className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-raised)] px-3 py-2 text-sm"
              />
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <button
              type="submit"
              className="rounded-full border border-[var(--color-border)] bg-[var(--color-surface-raised)] px-6 py-2 text-xs font-semibold uppercase tracking-[0.3em]"
              disabled={isFetching}
            >
              Apply Search
            </button>
            <button
              type="button"
              onClick={handleReset}
              className="rounded-full border border-[var(--color-border)] px-6 py-2 text-xs font-semibold uppercase tracking-[0.3em] text-[var(--color-text-muted)]"
            >
              Reset
            </button>
            <button
              type="button"
              onClick={() => refetch()}
              disabled={isFetching}
              className="rounded-full border border-[var(--color-border)] px-6 py-2 text-xs font-semibold uppercase tracking-[0.3em] disabled:opacity-50"
            >
              {isFetching ? "Refreshing" : "Refresh"}
            </button>
            <label className="inline-flex items-center gap-2 text-xs uppercase tracking-[0.3em] text-[var(--color-text-muted)]">
              <input
                type="checkbox"
                checked={includeArchived}
                onChange={(event) => {
                  setIncludeArchived(event.target.checked);
                  setPage(1);
                }}
                className="h-4 w-4 rounded border-[var(--color-border)]"
              />
              Include Archived
            </label>
            <span className="text-xs text-[var(--color-text-muted)]">
              Taxonomy data: {taxonomyStatus}
            </span>
          </div>
          <AppliedFilters filters={activeFilters} />
        </form>
      </section>

      <section className="space-y-4 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6">
        {isLoading && <EntriesLoadingState />}
        {isError && !isLoading && <EntriesErrorState onRetry={refetch} />}
        {!isLoading && !isError && data && items.length > 0 && (
          <>
            <EntriesTable items={items} />
            <PaginationControls
              page={currentPage}
              totalPages={totalPages}
              disablePrev={disablePrev}
              disableNext={disableNext}
              onPrev={() => setPage((prev) => Math.max(prev - 1, 1))}
              onNext={() => setPage((prev) => prev + 1)}
              start={start}
              end={end}
              totalItems={totalItems}
            />
          </>
        )}
        {!isLoading && !isError && data && items.length === 0 && (
          <EntriesEmptyState />
        )}
      </section>
    </div>
  );
};
