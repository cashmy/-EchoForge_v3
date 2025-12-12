import clsx from "clsx";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { NavLink } from "react-router-dom";
import type { LucideIcon } from "lucide-react";
import { AlertTriangle, Layers, Network, RefreshCcw } from "lucide-react";
import {
  TaxonomyCreatePayload,
  TaxonomyRecord,
  TaxonomyUpdatePayload,
} from "../api/taxonomy";
import { Modal } from "../components/Modal";
import { useTaxonomyManagement } from "../hooks/useTaxonomyManagement";

interface FormValues {
  id: string;
  label: string;
  name?: string;
  description?: string;
  sort_order: number;
  active: boolean;
}

const defaultFormValues: FormValues = {
  id: "",
  label: "",
  name: "",
  description: "",
  sort_order: 500,
  active: true,
};

const slugify = (value: string) =>
  value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80);

const statusChip = (active: boolean) =>
  active ? (
    <span className="rounded-full border border-emerald-500/40 bg-emerald-500/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.3em] text-emerald-600">
      Active
    </span>
  ) : (
    <span className="rounded-full border border-amber-500/40 bg-amber-500/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.3em] text-amber-600">
      Inactive
    </span>
  );

const TaxonomyCard = ({
  record,
  onEdit,
  onDelete,
  resourceLabel,
}: {
  record: TaxonomyRecord;
  onEdit: (record: TaxonomyRecord) => void;
  onDelete: (record: TaxonomyRecord) => void;
  resourceLabel: string;
}) => (
  <article className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5 shadow-[0_20px_40px_rgba(2,6,23,0.25)]">
    <div className="flex items-center justify-between gap-3">
      <div>
        <p className="text-xs uppercase tracking-[0.3em] text-[var(--color-text-muted)]">
          {resourceLabel}
        </p>
        <h3 className="text-lg font-semibold text-[var(--color-text)]">
          {record.label}
        </h3>
      </div>
      {statusChip(record.active)}
    </div>
    {record.description && (
      <p className="mt-3 text-sm text-[var(--color-text-muted)]">
        {record.description}
      </p>
    )}
    <div className="mt-4 flex flex-wrap gap-3 text-xs font-semibold uppercase tracking-[0.3em]">
      <button
        type="button"
        className="rounded-full border border-[var(--color-border)] px-4 py-1"
        onClick={() => onEdit(record)}
      >
        Edit
      </button>
      <button
        type="button"
        className="rounded-full border border-rose-400/60 px-4 py-1 text-rose-600"
        onClick={() => onDelete(record)}
      >
        Delete
      </button>
    </div>
  </article>
);

const TaxonomyFormModal = ({
  mode,
  record,
  open,
  onClose,
  onSubmit,
  busy,
  error,
  resourceLabel,
}: {
  mode: "create" | "edit";
  record: FormValues;
  open: boolean;
  onClose: () => void;
  onSubmit: (values: FormValues) => Promise<void>;
  busy: boolean;
  error: string | null;
  resourceLabel: string;
}) => {
  const [formValues, setFormValues] = useState<FormValues>(record);

  useEffect(() => {
    setFormValues(record);
  }, [record, open]);

  const updateField = (
    key: keyof FormValues,
    value: string | boolean | number
  ) => {
    setFormValues((prev) => ({
      ...prev,
      [key]: value,
    }));
  };

  const handleLabelChange = (nextLabel: string) => {
    setFormValues((prev) => {
      if (mode === "create") {
        const slug = slugify(nextLabel);
        return {
          ...prev,
          label: nextLabel,
          id: slug,
          name: slug,
        };
      }
      return {
        ...prev,
        label: nextLabel,
      };
    });
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    await onSubmit(formValues);
  };

  return (
    <Modal
      open={open}
      title={
        mode === "create" ? `Add ${resourceLabel}` : `Edit ${resourceLabel}`
      }
      onClose={onClose}
      footer={
        <>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full border border-[var(--color-border)] px-4 py-2 text-xs font-semibold uppercase tracking-[0.3em]"
            disabled={busy}
          >
            Cancel
          </button>
          <button
            type="submit"
            form="taxonomy-form"
            className="rounded-full border border-[var(--color-accent)] bg-[var(--color-accent)]/10 px-4 py-2 text-xs font-semibold uppercase tracking-[0.3em] text-[var(--color-accent)]"
            disabled={busy}
          >
            {busy ? "Saving" : "Save"}
          </button>
        </>
      }
    >
      <form id="taxonomy-form" className="space-y-4" onSubmit={handleSubmit}>
        <p className="rounded-2xl border border-dashed border-[var(--color-border)] bg-[var(--color-surface-raised)]/40 px-4 py-3 text-xs text-[var(--color-text-muted)]">
          ID, internal name, and weight are system-managed for now. We will
          auto-generate them from your label.
        </p>
        <div className="flex flex-col gap-1">
          <label className="text-xs uppercase tracking-[0.3em] text-[var(--color-text-muted)]">
            {resourceLabel} Label
          </label>
          <input
            type="text"
            value={formValues.label}
            onChange={(event) => handleLabelChange(event.target.value)}
            required
            className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-raised)] px-3 py-2 text-sm"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs uppercase tracking-[0.3em] text-[var(--color-text-muted)]">
            Description
          </label>
          <textarea
            value={formValues.description ?? ""}
            onChange={(event) => updateField("description", event.target.value)}
            className="h-24 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-raised)] px-3 py-2 text-sm"
          />
        </div>
        <label className="flex items-center gap-2 text-xs uppercase tracking-[0.3em] text-[var(--color-text-muted)]">
          <input
            type="checkbox"
            checked={formValues.active}
            onChange={(event) => updateField("active", event.target.checked)}
            className="h-4 w-4 rounded border-[var(--color-border)]"
          />
          Active
        </label>
        {error && <p className="text-sm text-rose-600">{error}</p>}
      </form>
    </Modal>
  );
};

const ConfirmDeleteModal = ({
  record,
  open,
  onClose,
  onConfirm,
  busy,
  error,
  resourceLabel,
}: {
  record: TaxonomyRecord | null;
  open: boolean;
  onClose: () => void;
  onConfirm: () => Promise<void>;
  busy: boolean;
  error: string | null;
  resourceLabel: string;
}) => (
  <Modal
    open={open}
    title={`Delete ${resourceLabel}`}
    onClose={onClose}
    footer={
      <>
        <button
          type="button"
          onClick={onClose}
          className="rounded-full border border-[var(--color-border)] px-4 py-2 text-xs font-semibold uppercase tracking-[0.3em]"
          disabled={busy}
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={onConfirm}
          className="rounded-full border border-rose-500 bg-rose-500/10 px-4 py-2 text-xs font-semibold uppercase tracking-[0.3em] text-rose-600"
          disabled={busy}
        >
          {busy ? "Deleting" : "Delete"}
        </button>
      </>
    }
  >
    <p className="text-sm text-[var(--color-text)]">
      Are you sure you want to delete <strong>{record?.label}</strong>? This
      action cannot be undone.
    </p>
    {error && <p className="mt-3 text-sm text-rose-600">{error}</p>}
  </Modal>
);

const taxonomyTabs = [
  { to: "/taxonomy/types", label: "Types" },
  { to: "/taxonomy/domains", label: "Domains" },
];

const TaxonomyTabs = () => (
  <div className="flex flex-wrap gap-3">
    {taxonomyTabs.map((tab) => (
      <NavLink
        key={tab.to}
        to={tab.to}
        className={({ isActive }) =>
          clsx(
            "rounded-full border px-4 py-2 text-xs font-semibold uppercase tracking-[0.3em]",
            isActive
              ? "border-[var(--color-accent)] bg-[var(--color-accent)]/10 text-[var(--color-accent)]"
              : "border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
          )
        }
      >
        {tab.label}
      </NavLink>
    ))}
  </div>
);

interface TaxonomyPageConfig {
  kind: "types" | "domains";
  title: string;
  subtitle: string;
  resourceSingular: string;
  resourcePlural: string;
  addButtonLabel: string;
  emptyStateText: string;
  icon: LucideIcon;
}

const taxonomyConfigs: Record<"types" | "domains", TaxonomyPageConfig> = {
  types: {
    kind: "types",
    title: "Entry Types",
    subtitle: "Manage reusable type labels across the pipeline.",
    resourceSingular: "Type",
    resourcePlural: "Types",
    addButtonLabel: "Add Type",
    emptyStateText: "No matching types. Adjust filters or add a new type.",
    icon: Layers,
  },
  domains: {
    kind: "domains",
    title: "Entry Domains",
    subtitle: "Organize focus areas and topic groupings.",
    resourceSingular: "Domain",
    resourcePlural: "Domains",
    addButtonLabel: "Add Domain",
    emptyStateText: "No matching domains. Adjust filters or add a new domain.",
    icon: Network,
  },
};

const TaxonomyManagerPage = (config: TaxonomyPageConfig) => {
  const Icon = config.icon;
  const [includeInactive, setIncludeInactive] = useState(false);
  const [search, setSearch] = useState("");
  const [modalMode, setModalMode] = useState<"create" | "edit" | null>(null);
  const [formState, setFormState] = useState<FormValues>(defaultFormValues);
  const [deleteTarget, setDeleteTarget] = useState<TaxonomyRecord | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const {
    records,
    isLoading,
    isError,
    refetch,
    createRecord,
    updateRecord,
    deleteRecord,
    isCreating,
    isUpdating,
    isDeleting,
  } = useTaxonomyManagement(config.kind, { includeInactive });

  const filteredRecords = useMemo(() => {
    const needle = search.trim().toLowerCase();
    if (!needle) {
      return records;
    }
    return records.filter((record) =>
      [record.label, record.id, record.description ?? ""].some((value) =>
        value.toLowerCase().includes(needle)
      )
    );
  }, [records, search]);

  const openCreateModal = () => {
    setFormError(null);
    setFormState(defaultFormValues);
    setModalMode("create");
  };

  const openEditModal = (record: TaxonomyRecord) => {
    setFormError(null);
    setFormState({
      id: record.id,
      label: record.label,
      name: record.name ?? "",
      description: record.description ?? "",
      sort_order: record.sort_order,
      active: record.active,
    });
    setModalMode("edit");
  };

  const closeFormModal = () => {
    setModalMode(null);
    setFormState(defaultFormValues);
  };

  const handleFormSubmit = async (values: FormValues) => {
    try {
      setFormError(null);
      if (modalMode === "create") {
        const computedId = values.id.trim() || slugify(values.label);
        if (!computedId) {
          setFormError("Unable to generate an ID. Please adjust the label.");
          return;
        }
        const payload: TaxonomyCreatePayload = {
          id: computedId,
          label: values.label.trim(),
          name: values.name?.trim() || computedId || undefined,
          description: values.description?.trim() || undefined,
          sort_order: values.sort_order,
          active: values.active,
        };
        await createRecord(payload);
      } else if (modalMode === "edit") {
        const payload: TaxonomyUpdatePayload = {
          label: values.label.trim(),
          name: values.name?.trim() || undefined,
          description: values.description?.trim() || undefined,
          sort_order: values.sort_order,
          active: values.active,
        };
        await updateRecord({ id: values.id, payload });
      }
      closeFormModal();
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Unable to save");
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) {
      return;
    }
    try {
      setDeleteError(null);
      await deleteRecord(deleteTarget.id);
      setDeleteTarget(null);
    } catch (error) {
      setDeleteError(error instanceof Error ? error.message : "Delete failed");
    }
  };

  const CardsGrid = () => {
    if (isLoading) {
      return (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {[1, 2, 3, 4, 5, 6].map((item) => (
            <div
              key={item}
              className="h-40 animate-pulse rounded-2xl border border-dashed border-[var(--color-border)] bg-[var(--color-surface)]"
            />
          ))}
        </div>
      );
    }
    if (isError) {
      return (
        <div className="flex items-center gap-3 rounded-2xl border border-rose-400/40 bg-rose-400/10 px-4 py-3 text-sm text-rose-700">
          <AlertTriangle className="h-4 w-4" />
          <span>Unable to load taxonomy records.</span>
          <button
            type="button"
            onClick={() => refetch()}
            className="ml-auto rounded-full border border-rose-500 px-3 py-1 text-xs font-semibold uppercase tracking-[0.3em]"
          >
            Retry
          </button>
        </div>
      );
    }
    if (filteredRecords.length === 0) {
      return (
        <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] px-6 py-12 text-center text-sm text-[var(--color-text-muted)]">
          {config.emptyStateText}
        </div>
      );
    }
    return (
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {filteredRecords.map((record) => (
          <TaxonomyCard
            key={record.id}
            record={record}
            onEdit={openEditModal}
            onDelete={setDeleteTarget}
            resourceLabel={config.resourceSingular}
          />
        ))}
      </div>
    );
  };

  const modalRecord = formState;
  const isSaving = modalMode === "create" ? isCreating : isUpdating;

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="flex items-center gap-2 text-xs uppercase tracking-[0.3em] text-[var(--color-text-muted)]">
            <Icon className="h-4 w-4" /> {config.resourcePlural}
          </p>
          <h1 className="text-2xl font-semibold text-[var(--color-text)]">
            {config.title}
          </h1>
          <p className="text-sm text-[var(--color-text-muted)]">
            {config.subtitle}
          </p>
        </div>
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            onClick={() => refetch()}
            className="inline-flex items-center gap-2 rounded-full border border-[var(--color-border)] px-4 py-2 text-xs font-semibold uppercase tracking-[0.3em]"
          >
            <RefreshCcw className="h-3 w-3" /> Refresh
          </button>
          <button
            type="button"
            onClick={openCreateModal}
            className="rounded-full border border-[var(--color-accent)] bg-[var(--color-accent)]/10 px-5 py-2 text-xs font-semibold uppercase tracking-[0.3em] text-[var(--color-accent)]"
          >
            {config.addButtonLabel}
          </button>
        </div>
      </header>

      <TaxonomyTabs />

      <section className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
        <div className="grid gap-4 md:grid-cols-3">
          <div className="flex flex-col gap-1 md:col-span-2">
            <label className="text-xs uppercase tracking-[0.3em] text-[var(--color-text-muted)]">
              Search
            </label>
            <input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Filter by label or description"
              className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-raised)] px-3 py-2 text-sm"
            />
          </div>
          <label className="mt-6 inline-flex items-center gap-2 text-xs uppercase tracking-[0.3em] text-[var(--color-text-muted)]">
            <input
              type="checkbox"
              checked={includeInactive}
              onChange={(event) => setIncludeInactive(event.target.checked)}
              className="h-4 w-4 rounded border-[var(--color-border)]"
            />
            Include inactive
          </label>
        </div>
      </section>

      <CardsGrid />

      {modalMode && (
        <TaxonomyFormModal
          mode={modalMode}
          record={modalRecord}
          open
          onClose={closeFormModal}
          onSubmit={handleFormSubmit}
          busy={isSaving}
          error={formError}
          resourceLabel={config.resourceSingular}
        />
      )}
      <ConfirmDeleteModal
        record={deleteTarget}
        open={Boolean(deleteTarget)}
        onClose={() => {
          setDeleteError(null);
          setDeleteTarget(null);
        }}
        onConfirm={handleDelete}
        busy={isDeleting}
        error={deleteError}
        resourceLabel={config.resourceSingular}
      />
    </div>
  );
};

export const TaxonomyTypesPage = () => (
  <TaxonomyManagerPage {...taxonomyConfigs.types} />
);

export const TaxonomyDomainsPage = () => (
  <TaxonomyManagerPage {...taxonomyConfigs.domains} />
);
