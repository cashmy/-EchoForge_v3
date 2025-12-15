import { AlertTriangle, RefreshCcw } from "lucide-react";
import { TaxonomyConsole } from "../components/TaxonomyConsole";
import { useDashboardSummary } from "../hooks/useDashboardSummary";
import type {
  DashboardSummaryResponse,
  NeedsReviewItem,
  RecentItem,
} from "../api/dashboard";
import { useAppStore } from "../state/useAppStore";
import { shouldShowTaxonomyConsole } from "../types/backend";

const EMPTY_PIPELINE: DashboardSummaryResponse["pipeline"] = {
  total: 0,
  by_ingest_state: {},
  failure_window: {
    since: "",
    counts: {},
  },
};

const EMPTY_COGNITIVE: DashboardSummaryResponse["cognitive"] = {
  by_status: {},
  needs_review: {
    items: [],
  },
};

const EMPTY_RECENT: DashboardSummaryResponse["recent"] = {
  processed: [],
};

const EMPTY_TAXONOMY: DashboardSummaryResponse["taxonomy"] = {
  top_types: [],
  top_domains: [],
};

const EMPTY_MOMENTUM: DashboardSummaryResponse["momentum"] = {
  recent_intake: [],
  source_mix: [],
};

const EMPTY_META: DashboardSummaryResponse["meta"] = {
  generated_at: "",
  time_window_days: 0,
  failure_window_days: 0,
  source_window_days: 0,
  include_archived: false,
};

const formatLabel = (value: string) =>
  value
    .replace(/_/g, " ")
    .replace(/\b(\w)/g, (match) => match.toUpperCase())
    .trim();

const formatDate = (value?: string) =>
  value
    ? new Date(value).toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
      })
    : "—";

const formatDateTime = (value?: string) =>
  value ? new Date(value).toLocaleString() : "—";

const formatCount = (value?: number) =>
  typeof value === "number" ? value.toLocaleString() : "0";

const RuntimeSnapshotCard = () => {
  const backendStatus = useAppStore((state) => state.backendStatus);
  const featureFlags = backendStatus?.featureFlags ?? {};
  const taxonomyEnabled = featureFlags.enable_taxonomy_refs_in_capture ?? false;

  return (
    <section className="rounded-3xl border border-[var(--color-border)] bg-[var(--color-surface)] p-8 shadow-[0_30px_90px_rgba(2,6,23,0.25)] transition-colors">
      <p className="text-xs uppercase tracking-[0.3em] text-[var(--color-text-muted)]">
        Runtime Snapshot
      </p>
      <div className="mt-3 flex flex-wrap items-center gap-4 text-3xl font-semibold text-[var(--color-text)]">
        {backendStatus?.environment ?? "unknown"}
        <span className="text-base font-normal text-[var(--color-text-muted)]">
          environment
        </span>
      </div>
      <dl className="mt-6 grid gap-4 text-sm text-[var(--color-text)] md:grid-cols-3">
        <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-raised)] p-4">
          <dt className="text-xs uppercase tracking-[0.3em] text-[var(--color-text-muted)]">
            EntryStore
          </dt>
          <dd className="mt-2 text-lg font-semibold text-[var(--color-text)]">
            {backendStatus?.entryStore ?? "pending"}
          </dd>
        </div>
        <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-raised)] p-4">
          <dt className="text-xs uppercase tracking-[0.3em] text-[var(--color-text-muted)]">
            Job Queue
          </dt>
          <dd className="mt-2 text-lg font-semibold text-[var(--color-text)]">
            {backendStatus?.jobQueue ?? "pending"}
          </dd>
        </div>
        <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-raised)] p-4">
          <dt className="text-xs uppercase tracking-[0.3em] text-[var(--color-text-muted)]">
            Taxonomy Capture Flag
          </dt>
          <dd
            className={
              taxonomyEnabled
                ? "mt-2 text-lg font-semibold text-[var(--color-success)]"
                : "mt-2 text-lg font-semibold text-amber-500"
            }
          >
            {taxonomyEnabled ? "enabled" : "disabled"}
          </dd>
        </div>
      </dl>
    </section>
  );
};

const SummaryHeader = ({
  meta,
  isFetching,
  onRefresh,
}: {
  meta?: DashboardSummaryResponse["meta"];
  isFetching: boolean;
  onRefresh: () => void;
}) => (
  <div className="flex flex-wrap items-center justify-between gap-4 rounded-3xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6">
    <div>
      <p className="text-xs uppercase tracking-[0.3em] text-[var(--color-text-muted)]">
        Dashboard Summary
      </p>
      <h2 className="text-2xl font-semibold text-[var(--color-text)]">
        Time window: {meta ? `${meta.time_window_days} days` : "pending"}
      </h2>
      <p className="text-sm text-[var(--color-text-muted)]">
        Generated {formatDateTime(meta?.generated_at)} • Failures tracked over{" "}
        {meta?.failure_window_days ?? "—"} days
      </p>
    </div>
    <button
      type="button"
      onClick={onRefresh}
      disabled={isFetching}
      className="inline-flex items-center gap-2 rounded-full border border-[var(--color-border)] bg-[var(--color-surface-raised)] px-4 py-2 text-sm font-semibold text-[var(--color-text)] disabled:opacity-60"
    >
      <RefreshCcw className={isFetching ? "h-4 w-4 animate-spin" : "h-4 w-4"} />
      {isFetching ? "Refreshing" : "Refresh"}
    </button>
  </div>
);

const DashboardLoadingState = () => (
  <div className="grid gap-4 md:grid-cols-2 animate-pulse">
    {[1, 2, 3, 4].map((item) => (
      <div
        key={item}
        className="h-32 rounded-3xl border border-dashed border-[var(--color-border)] bg-[var(--color-surface)]"
      />
    ))}
  </div>
);

const DashboardErrorState = ({ onRetry }: { onRetry: () => void }) => (
  <section className="flex items-center gap-4 rounded-3xl border border-rose-400/40 bg-rose-400/10 px-6 py-4 text-sm text-rose-700">
    <AlertTriangle className="h-4 w-4" />
    <span>Failed to load dashboard summary. Please try again.</span>
    <button
      type="button"
      onClick={onRetry}
      className="ml-auto rounded-full border border-rose-500 px-3 py-1 text-xs font-semibold uppercase tracking-widest"
    >
      Retry
    </button>
  </section>
);

const PipelineOverview = ({
  pipeline,
  meta,
}: {
  pipeline: DashboardSummaryResponse["pipeline"];
  meta: DashboardSummaryResponse["meta"];
}) => {
  const ingestEntries = Object.entries(pipeline.by_ingest_state ?? {});
  const failureCounts = pipeline.failure_window?.counts ?? {};
  const failureTotal = Object.values(failureCounts).reduce(
    (sum, value) => sum + value,
    0
  );

  return (
    <section className="rounded-3xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.3em] text-[var(--color-text-muted)]">
            Pipeline Overview
          </p>
          <h3 className="text-2xl font-semibold text-[var(--color-text)]">
            {formatCount(pipeline.total)} entries
          </h3>
        </div>
        <span className="text-xs text-[var(--color-text-muted)]">
          window {meta.time_window_days}d
        </span>
      </div>
      <ul className="mt-4 space-y-3">
        {ingestEntries.length === 0 && (
          <li className="text-sm text-[var(--color-text-muted)]">
            No pipeline data yet.
          </li>
        )}
        {ingestEntries.map(([status, count]) => (
          <li
            key={status}
            className="flex items-center justify-between rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-raised)] px-4 py-2 text-sm"
          >
            <span className="text-[var(--color-text-muted)]">
              {formatLabel(status)}
            </span>
            <span className="text-base font-semibold text-[var(--color-text)]">
              {formatCount(count)}
            </span>
          </li>
        ))}
      </ul>
      <div className="mt-4 rounded-2xl border border-dashed border-[var(--color-border)] bg-[var(--color-surface-raised)] px-4 py-3 text-sm text-[var(--color-text)]">
        Failures last {meta.failure_window_days}d: {formatCount(failureTotal)}
      </div>
    </section>
  );
};

const CognitiveOverview = ({
  cognitive,
}: {
  cognitive: DashboardSummaryResponse["cognitive"];
}) => {
  const statusEntries = Object.entries(cognitive.by_status ?? {});
  const needsReviewCount = cognitive.needs_review?.items.length ?? 0;

  return (
    <section className="rounded-3xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6">
      <p className="text-xs uppercase tracking-[0.3em] text-[var(--color-text-muted)]">
        Cognitive Status
      </p>
      <h3 className="text-2xl font-semibold text-[var(--color-text)]">
        {formatCount(statusEntries.reduce((sum, [, count]) => sum + count, 0))}{" "}
        tracked
      </h3>
      <ul className="mt-4 space-y-3">
        {statusEntries.length === 0 && (
          <li className="text-sm text-[var(--color-text-muted)]">
            No cognitive data.
          </li>
        )}
        {statusEntries.map(([status, count]) => (
          <li
            key={status}
            className="flex items-center justify-between text-sm"
          >
            <span className="text-[var(--color-text-muted)]">
              {formatLabel(status)}
            </span>
            <span className="text-base font-semibold text-[var(--color-text)]">
              {formatCount(count)}
            </span>
          </li>
        ))}
      </ul>
      <div className="mt-4 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-raised)] px-4 py-3 text-sm text-[var(--color-text)]">
        Needs review: {needsReviewCount}
      </div>
    </section>
  );
};

const NeedsReviewList = ({ items }: { items: NeedsReviewItem[] }) => {
  const list = items.slice(0, 5);
  return (
    <section className="rounded-3xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6">
      <p className="text-xs uppercase tracking-[0.3em] text-[var(--color-text-muted)]">
        Needs Review
      </p>
      <ul className="mt-4 space-y-3 text-sm">
        {list.length === 0 && (
          <li className="text-[var(--color-text-muted)]">
            No entries waiting for review.
          </li>
        )}
        {list.map((item) => (
          <li
            key={item.entry_id}
            className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-raised)] px-4 py-3"
          >
            <p className="font-semibold text-[var(--color-text)]">
              {item.display_title ?? "Untitled Entry"}
            </p>
            <p className="text-xs text-[var(--color-text-muted)]">
              {formatLabel(item.pipeline_status)} •{" "}
              {formatLabel(item.cognitive_status ?? "pending")}
            </p>
            <p className="text-xs text-[var(--color-text-muted)]">
              Updated {formatDateTime(item.updated_at)}
            </p>
          </li>
        ))}
      </ul>
    </section>
  );
};

const RecentProcessedList = ({ items }: { items: RecentItem[] }) => {
  const list = items.slice(0, 6);
  return (
    <section className="rounded-3xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6">
      <p className="text-xs uppercase tracking-[0.3em] text-[var(--color-text-muted)]">
        Recent Activity
      </p>
      <ul className="mt-4 space-y-3 text-sm">
        {list.length === 0 && (
          <li className="text-[var(--color-text-muted)]">
            No processed entries in this window.
          </li>
        )}
        {list.map((item) => (
          <li
            key={item.entry_id}
            className="flex items-center justify-between rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-raised)] px-4 py-3"
          >
            <div>
              <p className="font-semibold text-[var(--color-text)]">
                {item.display_title ?? "Untitled Entry"}
              </p>
              <p className="text-xs text-[var(--color-text-muted)]">
                {formatLabel(item.pipeline_status)}
              </p>
            </div>
            <span className="text-xs text-[var(--color-text-muted)]">
              {formatDateTime(item.updated_at)}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
};

const TaxonomyLeaders = ({
  taxonomy,
}: {
  taxonomy: DashboardSummaryResponse["taxonomy"];
}) => (
  <section className="rounded-3xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6">
    <p className="text-xs uppercase tracking-[0.3em] text-[var(--color-text-muted)]">
      Taxonomy Leaders
    </p>
    <div className="mt-4 grid gap-6 md:grid-cols-2">
      {[
        { title: "Types", items: taxonomy.top_types },
        { title: "Domains", items: taxonomy.top_domains },
      ].map(({ title, items }) => (
        <div key={title}>
          <h4 className="text-sm font-semibold text-[var(--color-text)]">
            {title}
          </h4>
          <ul className="mt-2 space-y-2 text-sm">
            {items.length === 0 && (
              <li className="text-[var(--color-text-muted)]">No data.</li>
            )}
            {items.map((item) => (
              <li
                key={`${title}-${item.id ?? item.label ?? "unknown"}`}
                className="flex items-center justify-between rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-raised)] px-3 py-2"
              >
                <span>{item.label ?? "Unlabeled"}</span>
                <span className="text-sm font-semibold text-[var(--color-text)]">
                  {formatCount(item.count)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  </section>
);

const MomentumPanel = ({
  momentum,
  meta,
}: {
  momentum: DashboardSummaryResponse["momentum"];
  meta: DashboardSummaryResponse["meta"];
}) => (
  <section className="rounded-3xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6">
    <p className="text-xs uppercase tracking-[0.3em] text-[var(--color-text-muted)]">
      Momentum
    </p>
    <div className="mt-4 grid gap-4 md:grid-cols-2">
      <div>
        <h4 className="text-sm font-semibold text-[var(--color-text)]">
          Recent Intake (last {meta.time_window_days}d)
        </h4>
        <ul className="mt-2 space-y-2 text-sm">
          {momentum.recent_intake.length === 0 && (
            <li className="text-[var(--color-text-muted)]">No intake data.</li>
          )}
          {momentum.recent_intake.map((item) => (
            <li
              key={`${item.date}-${item.count}`}
              className="flex items-center justify-between rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-raised)] px-3 py-2"
            >
              <span>{formatDate(item.date)}</span>
              <span className="text-sm font-semibold text-[var(--color-text)]">
                {formatCount(item.count)}
              </span>
            </li>
          ))}
        </ul>
      </div>
      <div>
        <h4 className="text-sm font-semibold text-[var(--color-text)]">
          Source Mix (last {meta.source_window_days}d)
        </h4>
        <ul className="mt-2 space-y-2 text-sm">
          {momentum.source_mix.length === 0 && (
            <li className="text-[var(--color-text-muted)]">No source data.</li>
          )}
          {momentum.source_mix.map((item) => (
            <li
              key={`${item.source_channel}-${item.count}`}
              className="flex items-center justify-between rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-raised)] px-3 py-2"
            >
              <span>{formatLabel(item.source_channel)}</span>
              <span className="text-sm font-semibold text-[var(--color-text)]">
                {formatCount(item.count)}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  </section>
);

export const DashboardPage = () => {
  const backendStatus = useAppStore((state) => state.backendStatus);
  const showTaxonomyConsole = shouldShowTaxonomyConsole(backendStatus);
  const { data, isLoading, isError, refetch, isFetching } =
    useDashboardSummary();
  const summary = data
    ? {
        meta: data.meta ?? EMPTY_META,
        pipeline: data.pipeline ?? EMPTY_PIPELINE,
        cognitive: data.cognitive ?? EMPTY_COGNITIVE,
        recent: data.recent ?? EMPTY_RECENT,
        taxonomy: data.taxonomy ?? EMPTY_TAXONOMY,
        momentum: data.momentum ?? EMPTY_MOMENTUM,
      }
    : undefined;

  return (
    <div className="space-y-10">
      <RuntimeSnapshotCard />

      <section className="space-y-6">
        <SummaryHeader
          meta={summary?.meta}
          isFetching={isFetching}
          onRefresh={refetch}
        />
        {isLoading && <DashboardLoadingState />}
        {isError && !isLoading && <DashboardErrorState onRetry={refetch} />}
        {summary && !isLoading && !isError && (
          <div className="space-y-6">
            <div className="grid gap-6 lg:grid-cols-3">
              <div className="lg:col-span-2">
                <PipelineOverview
                  pipeline={summary.pipeline}
                  meta={summary.meta}
                />
              </div>
              <CognitiveOverview cognitive={summary.cognitive} />
            </div>
            <div className="grid gap-6 lg:grid-cols-2">
              <NeedsReviewList
                items={summary.cognitive.needs_review?.items ?? []}
              />
              <RecentProcessedList items={summary.recent.processed} />
            </div>
            <div className="grid gap-6 lg:grid-cols-2">
              <TaxonomyLeaders taxonomy={summary.taxonomy} />
              <MomentumPanel momentum={summary.momentum} meta={summary.meta} />
            </div>
          </div>
        )}
      </section>

      {showTaxonomyConsole ? (
        <TaxonomyConsole />
      ) : (
        <section className="rounded-3xl border border-[var(--color-border)] bg-[var(--color-surface)] p-8 text-sm text-[var(--color-text)]">
          <p className="text-xs uppercase tracking-[0.3em] text-[var(--color-text-muted)]">
            Taxonomy Console
          </p>
          <p className="mt-2 text-base">
            Hidden for this profile while the capture workflow catches up. Flip
            the `enable_taxonomy_refs_in_capture` feature flag to preview the
            UI.
          </p>
        </section>
      )}
    </div>
  );
};
