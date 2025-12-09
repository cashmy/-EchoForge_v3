# EF-06 EntryStore Addendum — v1.2

---

## 0. Metadata

- **Artifact Name:** EF-06 EntryStore Addendum  
- **Short Name:** EF06_EntryStore_Addendum_v1.2  
- **Related Core Spec:** EF06_EntryStore_Spec_v1.1.md  
- **Version:** v1.2 (addendum)  
- **Status:** Active (Extends v1.1)  
- **Purpose:**  
  Clarify and extend EF-06 to fully support:
  - EF-01 idempotent ingestion  
  - M02 pipeline state transitions  
  - Future taxonomy and dashboard work  

This addendum does **not** replace v1.1; it refines and tightens behavior.  
If conflicts exist, **v1.2 addendum overrides v1.1** on the affected points below.

---

## 1. Ingestion Fingerprint Support

EF-06 MUST support storage of an ingestion fingerprint to enable EF-01 idempotency.

### 1.1 New Column (Conceptual)

- **Field:** `ingest_fingerprint`  
- **Type:** string / varchar (size implementation-specific, e.g., 128)  
- **Nullability:** nullable (older Entries may not have it)  
- **Semantics:**  
  - Stores a stable identifier derived from:  
    - File name  
    - File size  
    - Modification time and/or content hash  
  - Used *only* for idempotent ingestion decisions and traceability.

### 1.2 Indexing

EF-06 SHOULD provide an index or efficient query path over:

- `(source_channel, ingest_fingerprint)`  

to allow EF-01 to check for existing Entries with the same fingerprint and `source_channel` quickly.

---

## 2. Ingest State Machine Clarification

EF-06 v1.1 defines `ingest_state` conceptually.  
This addendum defines the **canonical allowed values** and expected transitions.

### 2.1 Allowed Values

- `captured`  
- `queued_for_transcription`  
- `queued_for_extraction`  
- `processing_transcription`  
- `processing_extraction`  
- `processing_normalization`  
- `processing_semantic`  
- `processed`  
- `failed`

### 2.2 Transition Rules (Conceptual)

Typical flows:

- Audio path:
  - `captured` → `queued_for_transcription` → `processing_transcription` →  
    - success → `processing_normalization` → `processing_semantic` → `processed`  
    - failure at any stage → `failed`

- Document path:
  - `captured` → `queued_for_extraction` → `processing_extraction` →  
    - success → `processing_normalization` → `processing_semantic` → `processed`  
    - failure at any stage → `failed`

EF-06 is the **source of truth** for `ingest_state`, even though EF-02/03/04/05 are responsible for updating it at each stage.

### 2.3 Ingest/Pipeline Pairing Matrix

Each coarse `ingest_state` value maps to a small, finite set of `pipeline_status` values. Workers MAY only persist combinations listed below.

| Phase | Ingest State | Allowed `pipeline_status` values | Notes |
| --- | --- | --- | --- |
| Capture accepted | `captured` | `captured`, `ingested` | Initial Entry creation via EF-01/API. |
| Audio queue | `queued_for_transcription` | `queued_for_transcription` | Entry handed to EF-02 watcher/job enqueue. |
| Audio processing | `processing_transcription` | `transcription_in_progress` | EF-02 actively transcribing. |
| Document queue | `queued_for_extraction` | `queued_for_extraction` | Entry waiting for EF-03 document worker. |
| Document processing | `processing_extraction` | `extraction_in_progress` | EF-03 actively extracting/ocr-ing. |
| Normalization intake (audio) | `processing_normalization` | `transcription_complete`, `queued_for_normalization` | EF-02 succeeded; EF-04 not yet started. |
| Normalization intake (document) | `processing_normalization` | `extraction_complete`, `queued_for_normalization` | EF-03 succeeded; EF-04 not yet started. |
| Normalization processing | `processing_normalization` | `normalization_in_progress` | EF-04 running. |
| Semantic intake | `processing_semantic` | `normalization_complete`, `queued_for_semantics` | EF-04 succeeded; EF-05 pending. |
| Semantic processing | `processing_semantic` | `semantic_in_progress` | EF-05 running. |
| Semantic complete | `processed` | `semantic_complete` | Terminal success (normal path). |
| Normalization-only complete | `processed` | `normalization_complete` | Allowed only when EF-05 is intentionally skipped. |
| Failure sink | `failed` | `transcription_failed`, `extraction_failed`, `normalization_failed`, `semantic_failed` | Any terminal error funnels here. |

### 2.4 Deterministic Transition Constraints

To keep telemetry deterministic, EF-06 enforces the following adjacency rules:

- `captured` → `queued_for_transcription` (audio) **or** `captured` → `queued_for_extraction` (documents). Mixed-mode Entries must pick exactly one.
- `queued_for_transcription` → `processing_transcription` → (`processing_normalization` on success | `failed` on terminal error).
- `queued_for_extraction` → `processing_extraction` → (`processing_normalization` on success | `failed` on terminal error).
- `processing_normalization` → `processing_semantic` (after EF-04 success) → `processed` (after EF-05 success).
- Any `processing_*` state may transition to `failed` with the matching `*_failed` pipeline status. Retrying a worker moves the Entry back to its corresponding `queued_for_*` ingest state.
- `processed` and `failed` are terminal unless an operator explicitly resets the Entry (human override protocol).

These rules are now encoded in shared helper constants (`backend/app/domain/ef06_entrystore/pipeline_states.py`) so EF-02/03/04/05 workers and governance tooling rely on a single source of truth.

---

## 3. Pipeline Output Fields

EF-06 MUST provide fields for pipeline outputs, at minimum:

- `transcription_text` — output of EF-02 (for audio)  
- `extracted_text` — output of EF-03 (for documents)  
- `normalized_text` — output of EF-04 (for all text)  
- `semantic_summary` — output of EF-05  
- `semantic_tags` — output of EF-05 (array or delimited string, implementation-specific)

If these fields already exist under slightly different names in v1.1, implementations MUST treat them as semantically equivalent. New deployments SHOULD adopt these canonical names.

---

## 4. Atomicity and Concurrency Note

EF-06 MUST ensure that:

- Updates to `ingest_state` and associated pipeline fields (e.g., `transcription_text`, `normalized_text`) are **atomic at the row level**.  
- Concurrent workers (EF-02/03/04/05) cannot partially overwrite each other’s changes in ways that leave the Entry in an invalid combination of states.

Implementation guidance (non-normative):

- Use row-level transactions around each pipeline update.  
- Optionally require that a worker’s `UPDATE` includes an expected prior `ingest_state` to avoid stale writes.

---

## 5. Search & Indexing (Ingestion-Focused)

In addition to any fields specified in v1.1, EF-06 SHOULD support efficient querying by:

- `ingest_state` (for pipeline dashboards and maintenance jobs)  
- `source_channel` and `source_type` (for debugging and audits)  
- `created_at` (for time-bounded queries)

Implementation details (e.g., actual index declarations) are left to the underlying DB (e.g., PostgreSQL), but Codex-LLM should assume these access patterns are efficient.

---

## 6. Versioning Note

- v1.1: core EntryStore schema and behavior  
- v1.2 (this addendum):  
  - Adds `ingest_fingerprint`  
  - Clarifies `ingest_state` lifecycle  
  - Canonicalizes pipeline output fields  
  - Adds concurrency/atomicity guidance

Future versions may further refine taxonomy fields, search structures, or performance tuning, but MUST remain compatible with v1.2 expectations.
---

## 7. Taxonomy Overlay (M03-T01)

M03 introduces canonical taxonomy tables and ID references so UI/API layers can present authoritative dropdowns while keeping existing label fields readable. These requirements extend §2.2/§2.3 of the v1.1 spec.

### 7.1 `entry_types` Table (Canonical Types)

EntryStore MUST manage an `entry_types` table (legacy name `type_labels`). The schema is:

| Column | Type | Constraints / Notes |
| --- | --- | --- |
| `id` | `VARCHAR(64)` | Primary key, canonical slug (e.g., `architecture_note`). Stable once created. |
| `name` | `VARCHAR(64)` | Short operator-facing code. MUST be unique (case-insensitive). Often matches `id` but may differ when IDs are immutable and names evolve. |
| `label` | `VARCHAR(128)` | Human-readable display text (e.g., `Architectural Note`). |
| `description` | `TEXT` | Optional guidance surfaced to UI tooling. |
| `active` | `BOOLEAN NOT NULL DEFAULT TRUE` | Controls dropdown visibility. `FALSE` hides from creation flows but does **not** erase prior references. |
| `sort_order` | `INTEGER NOT NULL DEFAULT 500` | Smaller numbers float earlier in UI lists; configurable per tenant/runtime. |
| `metadata` | `JSONB NULL` | Optional blob for UI hints (color, icon) or semantic mapping notes. |
| `created_at` / `updated_at` | `TIMESTAMPTZ NOT NULL` | Managed by EntryStore. |

Implementation notes:

- IDs are **canonical**: once EF-05 inference or a user assigns an `entry_types.id` to an Entry, that ID becomes the authoritative reference.  
- Free-form fields (`type_label`, `semantic_tags`) remain so Entries stay understandable even if the taxonomy row is deleted or not yet created.  
- Deleting (or deactivating) an `entry_types` row MUST NOT cascade into Entries; downstream clients fall back to the stored label if the ID no longer resolves.

### 7.2 `entries` Table Extensions

Two nullable columns are added to `entries` to hold loose references to taxonomy IDs:

```text
type_id   VARCHAR(64) NULL  -- references entry_types.id when present
domain_id VARCHAR(64) NULL  -- references entry_domains.id (M03-T02)
```

- These columns are **not** enforced with hard foreign keys in v1.2; they act as advisory pointers.  
- When both ID and label exist, clients prefer the ID for filtering/sorting and surface the label for display.  
- When EF-05 cannot map a label to a canonical ID, it writes only the label (no `type_id`). Operators can later reconcile by assigning the appropriate ID.

### 7.3 API / Worker Expectations

- EF-05 semantic worker: when classification output includes a known taxonomy entry, persist both `type_id` and `type_label`. If no ID is found, leave `type_id = NULL` but still populate `type_label` and `semantic_tags`.  
- EF-07 taxonomy endpoints (M03-T04/T05) MUST expose `entry_types` records with all fields above and honor `active` / `sort_order` semantics.  
- UI clients use `entry_types` for dropdowns and write the chosen `id` back via EF-07. If a user enters a custom label that does not match an existing ID, EF-07 records it as label-only until governance promotes it to a canonical entry.

### 7.4 Indexing & Governance

- Add indexes on `entry_types(active, sort_order)` and `entries(type_id)` so dashboards and filters remain performant.  
- Governance artifacts (decision logs, status logs) MUST capture taxonomy naming conventions and deletion policies (see M03-T12).  
- Future hierarchy/tag systems MUST build on these canonical IDs to maintain continuity with M03 assumptions.
