import { X } from "lucide-react";
import { useParams, Link } from "react-router-dom";
import { useEntryDetail } from "../hooks/useEntryDetail";
import { useUiLayoutStore } from "../state/useUiLayoutStore";

const PanelChrome = ({
  title,
  description,
}: {
  title: string;
  description: string;
}) => (
  <div className="flex h-full flex-col gap-4 px-6 py-6 text-[var(--color-text)]">
    <div>
      <p className="text-xs uppercase tracking-[0.3em] text-[var(--color-text-muted)]">
        {title}
      </p>
      <p className="mt-2 text-sm text-[var(--color-text-muted)]">
        {description}
      </p>
    </div>
  </div>
);

const EntryDetailPlaceholder = () => (
  <PanelChrome
    title="Entry Detail"
    description="Select an entry to preview summary, metadata, and semantic status."
  />
);

const WhisperSettingsPlaceholder = () => (
  <PanelChrome
    title="Whisper & Transcript"
    description="Runtime insight card that will surface transcription readiness once EF-04 wiring lands."
  />
);

const EntryDetailPreview = () => {
  const { entryId } = useParams<{ entryId?: string }>();
  const { data, isLoading, isError } = useEntryDetail(entryId);

  if (!entryId) {
    return <EntryDetailPlaceholder />;
  }
  if (isLoading) {
    return (
      <PanelChrome title="Entry Detail" description="Loading entry preview…" />
    );
  }
  if (isError || !data) {
    return (
      <PanelChrome
        title="Entry Detail"
        description="Unable to load preview data."
      />
    );
  }

  return (
    <div className="flex h-full flex-col gap-4 px-6 py-6 text-[var(--color-text)]">
      <div>
        <p className="text-xs uppercase tracking-[0.3em] text-[var(--color-text-muted)]">
          Entry Detail
        </p>
        <h3 className="mt-2 text-base font-semibold">
          {data.display_title ?? data.entry_id}
        </h3>
        <p className="text-xs text-[var(--color-text-muted)]">
          {data.entry_id}
        </p>
      </div>
      <div className="space-y-2 text-xs">
        <p>
          <strong className="font-semibold">Pipeline:</strong>{" "}
          {data.pipeline_status}
        </p>
        <p>
          <strong className="font-semibold">Cognitive:</strong>{" "}
          {data.cognitive_status}
        </p>
        <p>
          <strong className="font-semibold">Source:</strong>{" "}
          {data.source_channel}
        </p>
        <p>
          <strong className="font-semibold">Updated:</strong>{" "}
          {new Date(data.updated_at).toLocaleString()}
        </p>
      </div>
      {data.summary && (
        <p className="text-sm text-[var(--color-text-muted)]">{data.summary}</p>
      )}
      <Link
        to={`/entries/${data.entry_id}`}
        className="mt-auto inline-flex w-full items-center justify-center rounded-full border border-[var(--color-border)] px-4 py-2 text-xs font-semibold uppercase tracking-[0.3em] text-[var(--color-accent)]"
      >
        Open Detail
      </Link>
    </div>
  );
};

export const SecondaryPanel = () => {
  const secondaryPanelView = useUiLayoutStore(
    (state) => state.secondaryPanelView
  );
  const closeSecondaryPanel = useUiLayoutStore(
    (state) => state.closeSecondaryPanel
  );

  if (!secondaryPanelView) {
    return <div className="hidden xl:block xl:w-72" />;
  }

  return (
    <aside className="hidden w-80 border-l border-[var(--color-border)] bg-[var(--color-surface)] transition-colors xl:flex">
      <div className="flex h-full w-full flex-col">
        <div className="flex items-center justify-between border-b border-[var(--color-border)] px-6 py-4 text-[var(--color-text)]">
          <span className="text-sm font-semibold tracking-wide">
            {secondaryPanelView === "entry-detail"
              ? "Entry Detail"
              : "Whisper Status"}
          </span>
          <button
            type="button"
            onClick={closeSecondaryPanel}
            className="rounded-full border border-[var(--color-border)] bg-[var(--color-surface-raised)] p-1"
          >
            <X className="h-4 w-4" />
            <span className="sr-only">Close panel</span>
          </button>
        </div>
        <div className="flex-1 overflow-y-auto">
          {secondaryPanelView === "entry-detail" ? (
            <EntryDetailPreview />
          ) : (
            <WhisperSettingsPlaceholder />
          )}
        </div>
      </div>
    </aside>
  );
};
