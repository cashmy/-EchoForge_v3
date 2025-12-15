import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { CaptureRequestPayload } from "../api/capture";
import { submitCapture } from "../api/capture";

export const ManualEntryPage = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [title, setTitle] = useState("");
  const [sourceChannel, setSourceChannel] = useState("manual_text");
  const [mode, setMode] = useState<"text" | "file_ref">("text");
  const [content, setContent] = useState("");
  const [filePath, setFilePath] = useState("");
  const [notes, setNotes] = useState("");
  const [tagsInput, setTagsInput] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [successEntryId, setSuccessEntryId] = useState<string | null>(null);

  const captureMutation = useMutation({
    mutationFn: async (capturePayload: CaptureRequestPayload) =>
      submitCapture(capturePayload),
    onSuccess: (response) => {
      setSuccessEntryId(response.entry_id);
      queryClient.invalidateQueries({ queryKey: ["entries"] });
    },
  });

  const isSubmitting = captureMutation.isPending;

  const resetForm = () => {
    setTitle("");
    setSourceChannel("manual_text");
    setMode("text");
    setContent("");
    setFilePath("");
    setNotes("");
    setTagsInput("");
    setFormError(null);
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFormError(null);
    setSuccessEntryId(null);

    const trimmedTitle = title.trim();
    const trimmedChannel = sourceChannel.trim();
    const trimmedContent = content.trim();
    const trimmedFilePath = filePath.trim();

    if (!trimmedTitle) {
      setFormError("Title is required.");
      return;
    }
    if (mode === "text" && !trimmedContent) {
      setFormError("Please provide manual text content.");
      return;
    }
    if (mode === "file_ref" && !trimmedFilePath) {
      setFormError("File path is required when referencing a file.");
      return;
    }

    const metadata: Record<string, unknown> = {
      manual_entry_title: trimmedTitle,
      manual_entry_mode: mode,
    };
    if (trimmedChannel) {
      metadata.manual_entry_source_channel = trimmedChannel;
    }
    if (notes.trim()) {
      metadata.manual_entry_notes = notes.trim();
    }
    const tagList = tagsInput
      .split(",")
      .map((tag) => tag.trim())
      .filter(Boolean);
    if (tagList.length > 0) {
      metadata.manual_entry_tags = tagList;
    }
    if (mode === "file_ref" && trimmedFilePath) {
      metadata.manual_entry_file_path = trimmedFilePath;
    }

    const capturePayload: CaptureRequestPayload = {
      mode,
      source_channel: trimmedChannel || undefined,
      display_title: trimmedTitle,
      metadata: Object.keys(metadata).length ? metadata : undefined,
    };
    if (mode === "text") {
      capturePayload.content = trimmedContent;
    } else {
      capturePayload.file_path = trimmedFilePath;
    }

    try {
      await captureMutation.mutateAsync(capturePayload);
      resetForm();
    } catch (error) {
      setFormError(
        error instanceof Error ? error.message : "Unable to save entry."
      );
    }
  };

  return (
    <div className="space-y-6">
      <header className="space-y-3">
        <button
          type="button"
          onClick={() => navigate("/entries")}
          className="text-xs uppercase tracking-[0.3em] text-[var(--color-accent)] hover:underline"
        >
          ← Back to Entries
        </button>
        <div>
          <p className="text-xs uppercase tracking-[0.3em] text-[var(--color-text-muted)]">
            Manual Capture
          </p>
          <h1 className="text-3xl font-semibold text-[var(--color-text)]">
            Add Entry
          </h1>
          <p className="text-sm text-[var(--color-text-muted)]">
            Capture text or reference a file to seed the EchoForge pipeline. All
            fields support future EF-01 capture adapters.
          </p>
        </div>
      </header>

      {successEntryId && (
        <div className="rounded-2xl border border-emerald-500/40 bg-emerald-500/10 p-4 text-sm text-emerald-700">
          <p className="font-semibold">
            Entry created! ID:{" "}
            <span className="font-mono">{successEntryId}</span>
          </p>
          <div className="mt-3 flex flex-wrap gap-3 text-xs font-semibold uppercase tracking-[0.3em]">
            <button
              type="button"
              className="rounded-full border border-emerald-600 px-4 py-2 text-emerald-700"
              onClick={() => navigate(`/entries/${successEntryId}`)}
            >
              View Entry
            </button>
            <button
              type="button"
              className="rounded-full border border-[var(--color-border)] px-4 py-2 text-[var(--color-text)]"
              onClick={() => {
                setSuccessEntryId(null);
                resetForm();
              }}
            >
              Capture Another
            </button>
          </div>
        </div>
      )}

      {formError && (
        <div className="rounded-2xl border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-sm text-rose-600">
          {formError}
        </div>
      )}

      <form className="space-y-6" onSubmit={handleSubmit}>
        <section className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.3em] text-[var(--color-text-muted)]">
                Metadata
              </p>
              <h2 className="text-lg font-semibold text-[var(--color-text)]">
                Context & labeling
              </h2>
            </div>
          </div>
          <div className="mt-4 grid gap-4 md:grid-cols-2">
            <label className="flex flex-col gap-1 text-sm font-medium text-[var(--color-text)]">
              Title
              <input
                type="text"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-raised)] px-3 py-2"
                placeholder="e.g., Customer debrief notes"
                disabled={isSubmitting}
                required
              />
            </label>
            <label className="flex flex-col gap-1 text-sm font-medium text-[var(--color-text)]">
              Source Channel
              <input
                type="text"
                value={sourceChannel}
                onChange={(event) => setSourceChannel(event.target.value)}
                className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-raised)] px-3 py-2"
                placeholder="manual_text"
                disabled={isSubmitting}
              />
            </label>
          </div>
          <div className="mt-4 grid gap-4 md:grid-cols-2">
            <label className="flex flex-col gap-1 text-sm font-medium text-[var(--color-text)]">
              Notes (optional)
              <textarea
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
                className="h-24 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-raised)] px-3 py-2"
                placeholder="Internal notes, collection context, etc."
                disabled={isSubmitting}
              />
            </label>
            <label className="flex flex-col gap-1 text-sm font-medium text-[var(--color-text)]">
              Tags (comma-separated)
              <input
                type="text"
                value={tagsInput}
                onChange={(event) => setTagsInput(event.target.value)}
                className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-raised)] px-3 py-2"
                placeholder="finance, q4, follow-up"
                disabled={isSubmitting}
              />
            </label>
          </div>
        </section>

        <section className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
          <p className="text-xs uppercase tracking-[0.3em] text-[var(--color-text-muted)]">
            Content Source
          </p>
          <h2 className="text-lg font-semibold text-[var(--color-text)]">
            Provide text or reference a file
          </h2>
          <div className="mt-4 flex flex-wrap gap-4 text-sm font-semibold text-[var(--color-text)]">
            <label className="inline-flex items-center gap-2">
              <input
                type="radio"
                name="capture-mode"
                value="text"
                checked={mode === "text"}
                onChange={() => setMode("text")}
                disabled={isSubmitting}
              />
              Manual text
            </label>
            <label className="inline-flex items-center gap-2">
              <input
                type="radio"
                name="capture-mode"
                value="file_ref"
                checked={mode === "file_ref"}
                onChange={() => setMode("file_ref")}
                disabled={isSubmitting}
              />
              File reference
            </label>
          </div>
          {mode === "text" ? (
            <textarea
              value={content}
              onChange={(event) => setContent(event.target.value)}
              className="mt-4 h-48 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-raised)] px-4 py-3 text-sm"
              placeholder="Paste or type the entry content…"
              disabled={isSubmitting}
              required
            />
          ) : (
            <div className="mt-4 space-y-2">
              <input
                type="text"
                value={filePath}
                onChange={(event) => setFilePath(event.target.value)}
                className="w-full rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-raised)] px-4 py-2 text-sm"
                placeholder="C:\\path\\to\\document.pdf"
                disabled={isSubmitting}
                required
              />
              <p className="text-xs text-[var(--color-text-muted)]">
                EchoForge will fingerprint the file and enqueue transcription or
                extraction jobs based on the extension.
              </p>
            </div>
          )}
        </section>

        <section className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-xs uppercase tracking-[0.3em] text-[var(--color-text-muted)]">
                Submit
              </p>
              <h2 className="text-lg font-semibold text-[var(--color-text)]">
                Pipeline hand-off
              </h2>
            </div>
            <div className="flex gap-3">
              <button
                type="button"
                className="rounded-full border border-[var(--color-border)] px-4 py-2 text-xs font-semibold uppercase tracking-[0.3em]"
                onClick={resetForm}
                disabled={isSubmitting}
              >
                Reset
              </button>
              <button
                type="submit"
                className="rounded-full border border-[var(--color-accent)] bg-[var(--color-accent)]/10 px-6 py-2 text-xs font-semibold uppercase tracking-[0.3em] text-[var(--color-accent)]"
                disabled={isSubmitting}
              >
                {isSubmitting ? "Saving…" : "Create Entry"}
              </button>
            </div>
          </div>
          <p className="mt-4 text-sm text-[var(--color-text-muted)]">
            Once saved, entries appear in the main list within a few seconds.
            Capture metadata helps downstream automation but can be edited
            later.
          </p>
        </section>
      </form>
    </div>
  );
};
