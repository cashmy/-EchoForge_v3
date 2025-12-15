import { ReactNode, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useEntryDetail } from "../hooks/useEntryDetail";
import { useUiLayoutStore } from "../state/useUiLayoutStore";

const formatDateTime = (value?: string | null) =>
  value ? new Date(value).toLocaleString() : "—";

const formatLabel = (value?: string | null) => {
  if (!value) {
    return "—";
  }
  return value
    .replace(/_/g, " ")
    .replace(/\b(\w)/g, (match) => match.toUpperCase())
    .trim();
};

const formatStatus = (value?: string | null) => {
  if (!value) {
    return "Pending";
  }
  return formatLabel(value);
};

const formatPreview = (value?: string | null) => {
  const text = value?.trim();
  if (!text) {
    return "No preview captured yet.";
  }
  return text.length <= 600 ? text : `${text.slice(0, 600)}…`;
};

const formatBoolean = (value?: boolean) => {
  if (value === undefined) {
    return "—";
  }
  return value ? "Yes" : "No";
};

const readBooleanFlag = (value: unknown): boolean | undefined =>
  typeof value === "boolean" ? value : undefined;

const SectionCard = ({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) => (
  <section className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
    <p className="text-xs uppercase tracking-[0.3em] text-[var(--color-text-muted)]">
      {title}
    </p>
    <div className="mt-3 text-sm text-[var(--color-text)]">{children}</div>
  </section>
);

const InfoGrid = ({ items }: { items: { label: string; value: string }[] }) => (
  <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
    {items.map((item) => (
      <div
        key={item.label}
        className="rounded-xl bg-[var(--color-surface-raised)] px-4 py-3"
      >
        <dt className="text-xs uppercase tracking-[0.3em] text-[var(--color-text-muted)]">
          {item.label}
        </dt>
        <dd className="mt-1 text-sm font-medium text-[var(--color-text)]">
          {item.value}
        </dd>
      </div>
    ))}
  </dl>
);

const TextBlock = ({
  label,
  text,
  placeholder,
}: {
  label: string;
  text?: string | null;
  placeholder: string;
}) => (
  <SectionCard title={label}>
    <p className="whitespace-pre-wrap leading-relaxed">
      {text && text.trim().length > 0 ? text : placeholder}
    </p>
  </SectionCard>
);

export const EntryDetailPage = () => {
  const { entryId } = useParams<{ entryId: string }>();
  const [showExtraction, setShowExtraction] = useState(false);
  const [copyState, setCopyState] = useState<"idle" | "copied" | "error">(
    "idle"
  );
  const openSecondaryPanel = useUiLayoutStore(
    (state) => state.openSecondaryPanel
  );
  const closeSecondaryPanel = useUiLayoutStore(
    (state) => state.closeSecondaryPanel
  );

  useEffect(() => {
    if (entryId) {
      openSecondaryPanel("entry-detail");
    }
    return () => closeSecondaryPanel();
  }, [entryId, closeSecondaryPanel, openSecondaryPanel]);

  useEffect(() => {
    setShowExtraction(false);
    setCopyState("idle");
  }, [entryId]);

  const { data, isLoading, isError, refetch } = useEntryDetail(entryId);

  const archivedFlag = useMemo(() => {
    if (!data) {
      return undefined;
    }
    const metadataRecord = (data.metadata ?? {}) as Record<string, unknown>;
    const captureMetadataValue = metadataRecord["capture_metadata"];
    const captureMetadata =
      captureMetadataValue && typeof captureMetadataValue === "object"
        ? (captureMetadataValue as Record<string, unknown>)
        : undefined;
    return (
      readBooleanFlag(
        captureMetadata ? captureMetadata["is_archived"] : undefined
      ) ?? readBooleanFlag(metadataRecord["is_archived"])
    );
  }, [data]);

  const handleCopyEntryId = async () => {
    if (!data?.entry_id) {
      return;
    }
    if (
      typeof navigator === "undefined" ||
      !navigator.clipboard ||
      typeof navigator.clipboard.writeText !== "function"
    ) {
      setCopyState("error");
      return;
    }
    try {
      await navigator.clipboard.writeText(data.entry_id);
      setCopyState("copied");
      window.setTimeout(() => setCopyState("idle"), 2000);
    } catch (error) {
      console.error("copy_entry_id_failed", error);
      setCopyState("error");
      window.setTimeout(() => setCopyState("idle"), 2000);
    }
  };

  if (!entryId) {
    return (
      <section className="rounded-2xl border border-amber-500/40 bg-amber-500/10 px-6 py-4 text-[var(--color-text)]">
        Provide an entry id in the URL to load detail data.
      </section>
    );
  }

  if (isLoading) {
    return (
      <section className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] px-6 py-8 text-sm text-[var(--color-text-muted)]">
        Loading entry detail…
      </section>
    );
  }

  if (isError || !data) {
    return (
      <section className="space-y-3 rounded-2xl border border-rose-500/30 bg-rose-500/10 px-6 py-5 text-sm text-rose-700">
        <p>We could not load entry information right now.</p>
        <button
          type="button"
          onClick={() => refetch()}
          className="rounded-full border border-rose-500 px-4 py-1 text-xs font-semibold uppercase tracking-[0.3em]"
        >
          Retry
        </button>
      </section>
    );
  }

  const metadataItems = Object.entries(data.metadata ?? {}).map(
    ([key, value]) => ({
      label: key,
      value: typeof value === "string" ? value : JSON.stringify(value),
    })
  );

  const infoGridItems = [
    { label: "Type", value: data.type_label ?? "Unlabeled" },
    { label: "Domain", value: data.domain_label ?? "—" },
    { label: "Pipeline", value: formatLabel(data.pipeline_status) },
    { label: "Status", value: formatStatus(data.cognitive_status) },
    {
      label: "Ingest State",
      value: formatLabel(data.ingest_state ?? undefined),
    },
    { label: "Source Type", value: formatLabel(data.source_type) },
    { label: "Source Channel", value: formatLabel(data.source_channel) },
    { label: "Source Path", value: data.source_path ?? "—" },
    { label: "Content Language", value: data.content_lang ?? "—" },
    { label: "Created", value: formatDateTime(data.created_at) },
    { label: "Updated", value: formatDateTime(data.updated_at) },
    { label: "Summary Model", value: data.summary_model ?? "—" },
    { label: "Archived", value: formatBoolean(archivedFlag) },
  ];

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <div className="flex items-center gap-2 text-xs uppercase tracking-[0.3em] text-[var(--color-text-muted)]">
          <Link
            to="/entries"
            className="text-[var(--color-accent)] hover:underline"
          >
            Entries
          </Link>
          <span>/</span>
          <span>Entry Detail</span>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold text-[var(--color-text)]">
            {data.display_title ?? "Untitled Entry"}
          </h1>
          <button
            type="button"
            onClick={handleCopyEntryId}
            className="rounded-full border border-[var(--color-border)] px-3 py-1 text-xs uppercase tracking-[0.3em] text-[var(--color-text-muted)] hover:border-[var(--color-accent)]"
          >
            {copyState === "copied"
              ? "Entry ID Copied"
              : copyState === "error"
              ? "Copy Unavailable"
              : "Copy Entry ID"}
          </button>
        </div>
        <p className="text-sm text-[var(--color-text-muted)]">
          Inspect capture metadata, summaries, and transcript material for a
          single entry.
        </p>
      </header>

      <InfoGrid items={infoGridItems} />

      <SectionCard title="Summary">
        <p className="whitespace-pre-wrap leading-relaxed">
          {data.summary ?? data.verbatim_preview ?? "No summary available yet."}
        </p>
        {data.semantic_tags && data.semantic_tags.length > 0 && (
          <div className="mt-4 flex flex-wrap gap-2 text-xs">
            {data.semantic_tags.map((tag) => (
              <span
                key={tag}
                className="rounded-full border border-[var(--color-border)] bg-[var(--color-surface-raised)] px-3 py-1"
              >
                {tag}
              </span>
            ))}
          </div>
        )}
      </SectionCard>

      <TextBlock
        label="Source Preview"
        text={formatPreview(data.verbatim_preview)}
        placeholder="No preview captured yet."
      />

      <TextBlock
        label="Transcription Text"
        text={data.transcription_text}
        placeholder="No transcription captured for this entry yet."
      />
      <TextBlock
        label="Normalized Text"
        text={data.normalized_text}
        placeholder="Normalization has not produced text for this entry yet."
      />

      {data.extracted_text && (
        <SectionCard title="Document Extraction Text (debug)">
          {showExtraction ? (
            <div className="space-y-3 text-xs leading-relaxed text-[var(--color-text-muted)]">
              <button
                type="button"
                onClick={() => setShowExtraction(false)}
                className="rounded-full border border-[var(--color-border)] px-3 py-1 text-[var(--color-text)]"
              >
                Hide raw extraction
              </button>
              <p className="whitespace-pre-wrap text-[var(--color-text)]">
                {data.extracted_text}
              </p>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setShowExtraction(true)}
              className="rounded-full border border-dashed border-[var(--color-border)] px-3 py-1 text-xs uppercase tracking-[0.3em] text-[var(--color-text-muted)]"
            >
              Show raw extraction
            </button>
          )}
        </SectionCard>
      )}

      <SectionCard title="Metadata">
        {metadataItems.length === 0 ? (
          <p className="text-sm text-[var(--color-text-muted)]">
            No metadata captured.
          </p>
        ) : (
          <dl className="space-y-3">
            {metadataItems.map((item) => (
              <div key={item.label}>
                <dt className="text-xs uppercase tracking-[0.3em] text-[var(--color-text-muted)]">
                  {item.label}
                </dt>
                <dd className="mt-1 rounded-xl bg-[var(--color-surface-raised)] px-4 py-2 font-mono text-xs">
                  {item.value}
                </dd>
              </div>
            ))}
          </dl>
        )}
      </SectionCard>
    </div>
  );
};
