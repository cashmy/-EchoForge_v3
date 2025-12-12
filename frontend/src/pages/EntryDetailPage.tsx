import { ReactNode, useEffect } from "react";
import { Link, useParams } from "react-router-dom";
import { useEntryDetail } from "../hooks/useEntryDetail";
import { useUiLayoutStore } from "../state/useUiLayoutStore";

const formatDateTime = (value?: string | null) =>
  value ? new Date(value).toLocaleString() : "—";

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

  const { data, isLoading, isError, refetch } = useEntryDetail(entryId);

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
    { label: "Entry Id", value: data.entry_id },
    { label: "Type", value: data.type_label ?? data.type_id ?? "—" },
    { label: "Domain", value: data.domain_label ?? data.domain_id ?? "—" },
    { label: "Pipeline", value: data.pipeline_status },
    { label: "Cognitive", value: data.cognitive_status },
    { label: "Ingest State", value: data.ingest_state ?? "—" },
    { label: "Source Channel", value: data.source_channel },
    { label: "Source Path", value: data.source_path ?? "—" },
    { label: "Created", value: formatDateTime(data.created_at) },
    { label: "Updated", value: formatDateTime(data.updated_at) },
    { label: "Content Language", value: data.content_lang ?? "—" },
    {
      label: "Summary Model",
      value: data.summary_model ?? "—",
    },
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
        <h1 className="text-2xl font-semibold text-[var(--color-text)]">
          {data.display_title ?? data.entry_id}
        </h1>
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
        label="Transcription Text"
        text={data.transcription_text}
        placeholder="No transcription captured for this entry yet."
      />
      <TextBlock
        label="Extracted Text"
        text={data.extracted_text}
        placeholder="No extraction payload has been recorded."
      />
      <TextBlock
        label="Normalized Text"
        text={data.normalized_text}
        placeholder="Normalization has not produced text for this entry yet."
      />

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
