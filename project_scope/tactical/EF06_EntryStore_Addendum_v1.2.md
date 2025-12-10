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

#### Entry Domains Table (Canonical Domains)

M03-T02 introduces `entry_domains` (legacy: `domain_labels`) to provide the same canonical guarantees for domain classifications. Schema mirrors `entry_types` so workers/UI can treat both tables uniformly:

| Column | Type | Constraints / Notes |
| --- | --- | --- |
| `id` | `VARCHAR(64)` | Primary key slug (e.g., `architecture`). Lowercase kebab/pascal casing per taxonomy conventions; immutable once issued. |
| `name` | `VARCHAR(64)` | Short operator-facing code, unique (case-insensitive). Used in CLI/admin tooling. |
| `label` | `VARCHAR(128)` | Human-readable title displayed to end users (e.g., `Architecture`). |
| `description` | `TEXT` | Optional guidance describing when to use the domain. |
| `active` | `BOOLEAN NOT NULL DEFAULT TRUE` | Governs dropdown visibility; `FALSE` hides during creation but preserves historical assignments. |
| `sort_order` | `INTEGER NOT NULL DEFAULT 500` | Determines ordering within UI selectors; same semantics as `entry_types.sort_order`. |
| `metadata` | `JSONB NULL` | Optional blob for UI cues (icons, color tags) or semantic hints for EF-05 reconciliation. |
| `created_at` / `updated_at` | `TIMESTAMPTZ NOT NULL` | Managed by EntryStore triggers/defaults. |

Implementation notes:

- Column defaults, indexes, and auditing MUST match `entry_types` conventions so migrations/tests can share helpers.
- IDs are canonical references that EF-05/EF-07 treat as the source of truth when present; labels remain for readability and in case an ID is missing.
- Governance MAY pre-seed the table, but schema must allow runtime insertion via EF-07 `/api/domains` endpoints once SD04 lands.
- No hierarchy/parental linkage exists in v1.2; future revisions would add nullable pointers once specs define them.

### 7.2 `entries` Table Extensions

Two nullable columns are added to `entries` to hold loose references to taxonomy IDs:

```text
type_id   VARCHAR(64) NULL  -- references entry_types.id when present
domain_id VARCHAR(64) NULL  -- references entry_domains.id (M03-T02)
```

- These columns are **not** enforced with hard foreign keys in v1.2; they act as advisory pointers.  
- When both ID and label exist, clients prefer the ID for filtering/sorting and surface the label for display.  
- EF-05 (and any UI client) MUST write the matching label fields even when an ID is known so the entry remains legible if taxonomy rows disappear later.  
- When EF-05 cannot map a type/domain label to a canonical ID, it writes only the label (`type_label` / `domain_label`) and leaves the respective ID NULL. Operators or future reconciliation jobs can later assign the appropriate ID without losing the original free-form value.

#### 7.2.1 Referential Semantics & Soft Delete Behavior (ST02)

- `type_id` and `domain_id` are **canonical references**: once populated, EntryStore treats them as authoritative even if `type_label`/`domain_label` contain different text.  
- If the referenced taxonomy row is deactivated (`active = FALSE`), Entries retain the ID and continue to surface the stored label (`type_label` or `domain_label`) as a human-friendly fallback. UI layers SHOULD indicate “inactive” status but MUST NOT drop the ID automatically.  
- If a taxonomy row is hard-deleted, EntryStore leaves the Entry’s `type_id` / `domain_id` untouched (the ID becomes orphaned). EF-07 clients must handle this gracefully by falling back to free-form labels.  
- Governance policy (captured under M03-T12) determines whether hard deletes are allowed; EF-06 simply stores the dangling ID for auditability.  
- When reassigning taxonomy via API/worker flows, updates MUST set both the ID and label atomically so history remains consistent. This applies independently to both `type_id` and `domain_id`; partial updates (ID without label or vice versa) are rejected at the API surface.  
- UI clients MUST display `domain_label` whenever `domain_id` is NULL or points to a deactivated record, and SHOULD offer reconciliation affordances so operators can choose a canonical `entry_domains.id` later without losing historical context.  
- EF-05 SHOULD leave `domain_id` untouched when it cannot unambiguously determine the canonical domain; best-effort guesses belong in `domain_label`, avoiding accidental reclassification.

### 7.3 API / Worker Expectations

- **EF-05 semantic worker:** When classification output includes a known taxonomy entry, persist both `type_id`/`type_label` and `domain_id`/`domain_label`. If no canonical ID is found for either dimension, leave the corresponding ID NULL but still populate the labels and semantic metadata. Best-effort guesses for domains belong only in `domain_label` to avoid polluting canonical IDs.  
- **EF-07 taxonomy endpoints:** M03-T04/T05 MUST expose both `entry_types` and `entry_domains` collections with all schema fields defined in §7.1, honoring `active`, `sort_order`, and `metadata`. Responses SHOULD include pagination metadata and a `last_updated` cursor so UI caches can refresh efficiently.  
- **Domain-specific API contract:** `POST /api/domains` mirrors `/api/types`: required fields are `id` (slug), `label`; optional fields include `name`, `description`, `sort_order`, `active`, and `metadata`. `PATCH /api/domains/{id}` MAY update any mutable column except `id`. Attempting to change `id` yields `400`. Deleting a domain either toggles `active=false` (default) or performs a hard delete only when governance policies allow; the API MUST warn when dependent entries still reference the ID.  
- **Entry mutation payloads:** `POST /api/entries` and `PATCH /api/entries/{id}` MUST send taxonomy references as `{type_id, type_label}` and `{domain_id, domain_label}` pairs. Payloads with only one half of the pair are rejected (`422`) to keep EF-06 data consistent. UI clients that cannot supply an ID must explicitly set the ID field to `null` while retaining the label.  
- **Dropdown / UI behavior:** UI clients use `/api/types` and `/api/domains` for authoritative dropdowns, writing the chosen IDs back through EF-07. If a user enters a custom label that does not match an existing ID, EF-07 stores the label-only value and leaves the ID NULL until governance promotes it to a canonical entry. Clients MUST surface when a previously selected ID becomes inactive so operators can decide whether to keep or remap it.

### 7.4 Indexing & Governance

- Add indexes on `entry_types(active, sort_order)` and `entries(type_id)` so dashboards and filters remain performant.  
- Governance artifacts (decision logs, status logs) MUST capture taxonomy naming conventions and deletion policies (see M03-T12).  
- Future hierarchy/tag systems MUST build on these canonical IDs to maintain continuity with M03 assumptions.

### 7.5 Migration Blueprint (ST03)

- **Phase 1 — Schema & Table Prep:**
  - Create `entry_types` and `entry_domains` with the columns defined in §7.1 (renaming legacy `type_labels` / `domain_labels` only after data backfill is complete).  
  - If a legacy `domain_labels` table exists, add the missing columns (`id` slug, `active`, `sort_order`, `metadata`, timestamps) alongside the existing UUID primary key. Maintain writes through the old columns until Phase 2 finishes, then drop/rename legacy fields.  
  - Add nullable `type_id`/`domain_id` columns to `entries` plus indexes on `entries(type_id)` and `entries(domain_id)` to protect query plans.  
  - Add taxonomy-serving indexes: `entry_types(active, sort_order)`, `entry_domains(active, sort_order)` to keep dropdown queries cheap.
- **Phase 2 — Data Backfill & Canonicalization:**
  - Generate canonical slugs for every existing type/domain row using governance-approved naming rules; persist them into the new `id` column before enforcing NOT NULL.  
  - Copy existing descriptive text/metadata into the new schema, ensuring `active` defaults TRUE and `sort_order` inherits existing UI ordering (or uses 500 when unknown).  
  - For entries, leave `type_id`/`domain_id` NULL initially. A reconciliation script SHOULD capture the mapping between existing label strings and the new canonical IDs but **must not** rewrite entries until operators approve the mapping (see SD05 governance hooks).  
  - Ensure EF-05 continues to write `type_label`/`domain_label` throughout the migration; deploy a canary worker version that also attempts to set IDs when they exist, guarding on NULL columns to keep pre-migration deployments compatible.
- **Phase 3 — Application Wiring & Verification:**
  - Flip EF-05 and EF-07 to require `{type_id, type_label}` / `{domain_id, domain_label}` pairs once schema changes are live in all environments. API validation rejects payloads that set an ID without the matching label to avoid inconsistent state.  
  - Add smoke tests covering Entry creation/update with IDs, plus migration tests ensuring an Entry created pre-migration (labels only) can later accept an ID without data loss.  
  - Document a rollback plan: drop `type_id`/`domain_id` columns and revert workers to label-only mode if taxonomy tables need to be disabled, ensuring migrations are wrapped in transactional scripts so partial deployments can be rolled back cleanly.

### 7.6 Observability & Governance Hooks (ST05 / SD05)

Taxonomy changes are governance-sensitive because they alter dropdowns, semantic hints, and referential integrity guarantees. EF-06 therefore MUST surface deterministically auditable telemetry any time Types or Domains mutate.

#### 7.6.1 Logging & Capture Events

- All mutations to `entry_types` and `entry_domains` MUST emit an INF-03 capture event *and* a structured log line. Required event topics:
  - `taxonomy.type.created`, `taxonomy.type.updated`, `taxonomy.type.deactivated`, `taxonomy.type.reactivated`, `taxonomy.type.deleted`
  - `taxonomy.domain.created`, `taxonomy.domain.updated`, `taxonomy.domain.deactivated`, `taxonomy.domain.reactivated`, `taxonomy.domain.deleted`
- Each payload MUST include: `taxonomy_id`, `resource` (`type` | `domain`), `action`, `actor_id`/`actor_source`, `changes` (before/after diff), `referenced_entries` (count at mutation time), and `allow_taxonomy_delete` flag state. These payloads allow ETS-API cases to assert that delete gating and warning logic fired.
- Structured log lines SHOULD reuse the same fields plus a monotonic `event_id` for cross-correlation. Logs MUST be written at INFO level for create/update and WARN for delete/deactivate operations.

#### 7.6.2 Metrics & ETS Coverage

- EF-06 MUST expose counters (via existing metrics emitter) for:
  - `taxonomy_type_total` / `taxonomy_domain_total` (current active rows)
  - `taxonomy_delete_blocked_total` (incremented whenever a delete attempt is rejected because dependencies exist or `ALLOW_TAXONOMY_DELETE` is `false`)
  - `taxonomy_reconciliation_pending` (number of Entries whose `type_id`/`domain_id` is NULL while labels are non-null)
- ETS scenarios map as follows:
  - `ETS-DB-TAX-01` validates the `entry_types` telemetry (creation + deactivate + delete).
  - `ETS-DB-TAX-02` mirrors the same for `entry_domains`.
  - `ETS-API-TAX-01` asserts that API responses surface `deletion_warning` metadata when `referenced_entries > 0` and that the matching capture events/logs exist. ETS harnesses MUST be able to query capture-event storage using the topics above.

#### 7.6.3 Governance Toggles & Workflows

- A single configuration flag (`ALLOW_TAXONOMY_DELETE`, surfaced through INF-01) controls whether hard deletes are permitted in a runtime. EF-06/EF-07 MUST read this flag per request and block DELETE operations (HTTP 403 + structured warning) when false; deactivate remains allowed.
- When a delete is allowed, EF-06 MUST capture `referenced_entries` count and include it in both the API response and the capture event so operators can prove that dangling IDs were acceptable at decision time.
- Operators MUST document irreversible decisions (mass delete, renaming canonical IDs) in `pm/decisions/` referencing the event IDs emitted above. EF-06 therefore needs to store capture-event IDs (or log correlation IDs) alongside the mutation transaction so governance tooling can surface them later. Implementation note: persist `last_audit_event_id` columns on `entry_types`/`entry_domains` or make them derivable via INF-03 payloads.
- Reconciliation jobs that backfill `type_id`/`domain_id` from labels count as mutations and MUST emit the `...updated` events with `changes.source = reconciliation`. This keeps the audit trail consistent with interactive API usage.
