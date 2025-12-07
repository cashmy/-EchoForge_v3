# M03 — Taxonomy & Classification Integration — v1.1

---

## 0. Metadata

- **Milestone ID:** M03  
- **Milestone Name:** Taxonomy & Classification Layer  
- **Version:** v1.1  
- **Scope Summary:**  
  Establish user-defined, flexible classification structures for Entries:
  - Type table (what *kind* of entry this is)  
  - Domain table (what *topic area* it belongs to)  
  - EF-06 integration for storing references  
  - EF-07 taxonomy APIs aligned with `EF07_Api_Contract_v1.2.md`  
  - UI/API considerations for dynamic taxonomies and dropdowns  
  - Codex-LLM–safe update patterns

Taxonomy is a **soft overlay**: Entries remain meaningful via their own fields even if taxonomy values are deleted or repurposed.

- **Primary Components:**  
  - EF-06 EntryStore (schema extension)  
  - Taxonomy Tables: `EntryType`, `EntryDomain`  
  - EF-07 (`/api/types`, `/api/domains`, `/api/entries`)  
  - EF-05 (optional support for semantic suggestions)  
- **Governance:**  
  - Milestone_Task_Subsystem_v1.1.md  
  - EnaC_TestingSubsystem_v1.0.md  

---

## 1. Status Tracking Model

Each task contains a Status Block:

```markdown
- **Status:** pending  <!-- pending | in_progress | blocked | deferred | done -->
- **Last Updated:** —
- **Notes:** —
```

Codex-LLM MUST only mutate these three fields.

---

## 2. References

- `EF06_EntryStore_Spec_v1.1.md`  
- `EF06_EntryStore_Addendum_v1.2.md`  
- `EF05_GptEntrySemanticService_Spec_v1.0.md`  
- `EF04_EF05_Interface_Note_v1.0.md`  
- `EF07_Api_Contract_v1.2.md`  
- `EchoForge_Architecture_Overview_v1.1.md`  

---

## 3. Tasks

---

### M03-T01 — Define Type Table (EntryType) Schema

- **Type:** design  
- **Depends On:** EF-06 v1.2  
- **ETS Profiles:** ETS-DB  
- **Status Block:**  
  - **Status:** pending  
  - **Last Updated:** —  
  - **Notes:** —  

**Description:**  
Define a flexible schema for the Type table, including fields minimally:
- `id` (string PK; often same as `name`)  
- `name` (short code)  
- `label` (user-friendly name)  
- `description` (optional)  
- `active` (bool, for dropdown visibility)  
- `sort_order` (int, for UI ordering)  
- `created_at` / `updated_at`  

Note in the spec that Types are **advisory**: Entries are not required to reference a Type.

---

### M03-T02 — Define Domain Table (EntryDomain) Schema

- **Type:** design  
- **Depends On:** M03-T01  
- **ETS Profiles:** ETS-DB  
- **Status Block:**  
  - **Status:** pending  
  - **Last Updated:** —  
  - **Notes:** —  

**Description:**  
Define Domain taxonomy similarly:
- `id`  
- `name`  
- `label`  
- `description`  
- `active`  
- `sort_order`  
- `created_at` / `updated_at`  

Hierarchy is optional and out-of-scope for v1.1 (Domains are flat in this version).

---

### M03-T03 — Extend EF-06 Schema with Taxonomy Reference Fields

- **Type:** design / implementation  
- **Depends On:** M03-T01, M03-T02  
- **ETS Profiles:** ETS-DB  
- **Status Block:**  
  - **Status:** pending  
  - **Last Updated:** —  
  - **Notes:** —  

**Description:**  
Extend EF-06 to include optional reference fields:

- `type_id` (nullable string)  
- `domain_id` (nullable string)  

plus any free-form fields already defined (e.g., `type_label`, `domain_label`).  

Document clearly:

- Entries remain meaningful based on free-form labels even if the referenced Type/Domain is deleted.  
- `type_id` and `domain_id` are hints for normalization and filtering, not strict foreign keys.

---

### M03-T04 — Define EF-07 Taxonomy API Contracts (Types/Domains)

- **Type:** design  
- **Depends On:** M03-T01, M03-T02, EF07 v1.2  
- **ETS Profiles:** ETS-API  
- **Status Block:**  
  - **Status:** pending  
  - **Last Updated:** —  
  - **Notes:** —  

**Description:**  
Align EF-07 taxonomy behavior with `EF07_Api_Contract_v1.2.md`:

- Types:
  - `GET /api/types`
  - `POST /api/types`
  - `PATCH /api/types/{type_id}`
  - `DELETE /api/types/{type_id}`

- Domains:
  - `GET /api/domains`
  - `POST /api/domains`
  - `PATCH /api/domains/{domain_id}`
  - `DELETE /api/domains/{domain_id}`

Clarify in the spec:

- `active = false` controls dropdown visibility.  
- `DELETE` removes the taxonomy row but does not invalidate existing entries; clients must handle dangling IDs gracefully.

---

### M03-T05 — Implement Taxonomy CRUD Endpoints (EF-07)

- **Type:** implementation  
- **Depends On:** M03-T04  
- **ETS Profiles:** ETS-API  
- **Status Block:**  
  - **Status:** pending  
  - **Last Updated:** —  
  - **Notes:** —  

**Description:**  
Implement `GET/POST/PATCH/DELETE` for Types and Domains per EF07 v1.2:

- Input validation (id uniqueness, required fields).  
- Soft delete via `active: false`.  
- Hard delete via `DELETE` (optional, but supported).  
- Logging via INF-03.

---

### M03-T06 — Define Entry Classification Update Mechanisms (Conceptual)

- **Type:** design  
- **Depends On:** M03-T03, EF07 v1.2  
- **ETS Profiles:** ETS-API, ETS-UI  
- **Status Block:**  
  - **Status:** pending  
  - **Last Updated:** —  
  - **Notes:** —  

**Description:**  
Define how Entries will be classified and reclassified using taxonomy:

- For capture flows (`/api/capture`), specify how `metadata` MAY include:
  - free-form type/domain labels, and/or  
  - desired `type_id` / `domain_id`.  

- For future editing flows (e.g., an `/api/entries` update capability in EF07 v1.x or v2.x):
  - Specify desired payload shape for setting/changing `type_id`/`domain_id`.  
  - Mark this as **future API work**, not part of v1.2 endpoints yet.

The goal is to give Codex-LLM a clear conceptual contract for how classification should be applied, while keeping EF07 v1.2’s concrete API surface unchanged.

---

### M03-T07 — Implement Taxonomy Retrieval for UI Client

- **Type:** implementation  
- **Depends On:** M03-T05  
- **ETS Profiles:** ETS-API, ETS-UI  
- **Status Block:**  
  - **Status:** pending  
  - **Last Updated:** —  
  - **Notes:** —  

**Description:**  
Ensure the Electron/SPA client can hydrate dropdowns and filter controls by calling:

- `GET /api/types`  
- `GET /api/domains`

Define any minimal client-side caching behavior and how “inactive” taxonomy values (`active = false`) should be treated in:

- New entry creation  
- Editing existing entries that still reference deactivated IDs

---

### M03-T08 — EF-05 Semantic Suggestions (Optional in v1.1)

- **Type:** design  
- **Depends On:** EF-05, M02  
- **ETS Profiles:** ETS-LLM  
- **Status Block:**  
  - **Status:** pending  
  - **Last Updated:** —  
  - **Notes:** —  

**Description:**  
Define minimal semantic “hints” capability:

- EF-05 MAY propose suggested Type/Domain labels/IDs based on `normalized_text`.  
- EF-05 MUST NOT auto-assign taxonomy to Entries.  
- Suggested classifications MUST be surfaced to the UI as **non-authoritative hints** that the user can accept or ignore.

Document any changes needed in EF-05’s result shape to support this (e.g., `suggested_type_ids`, `suggested_domain_ids`).

---

### M03-T09 — Add Indexing Over Taxonomy in EF-06

- **Type:** implementation  
- **Depends On:** M03-T03  
- **ETS Profiles:** ETS-DB  
- **Status Block:**  
  - **Status:** pending  
  - **Last Updated:** —  
  - **Notes:** —  

**Description:**  
Create indexes over:

- `type_id`  
- `domain_id`  

to support:

- Dashboard summary queries  
- UI filtering for entry lists  
- Efficient taxonomy-based searches.

---

### M03-T10 — Implement ETS Cases for Taxonomy

- **Type:** test  
- **Depends On:** M03-T05 through M03-T09  
- **ETS Profiles:** ETS-API, ETS-DB  
- **Status Block:**  
  - **Status:** pending  
  - **Last Updated:** —  
  - **Notes:** —  

**Description:**  
Define and/or implement ETS test cases to validate:

- CRUD behavior for Types and Domains.  
- Soft-delete visibility behavior (`active = false`).  
- Behavior when Entries reference deleted taxonomy IDs.  
- Correct indexing and filtering in EF-06 for `type_id` and `domain_id`.  
- Semantic suggestion flows (if M03-T08 is implemented).

---

### M03-T11 — Generate Status Log for M03

- **Type:** governance  
- **Depends On:** At least some tasks in progress  
- **ETS Profiles:** —  
- **Status Block:**  
  - **Status:** pending  
  - **Last Updated:** —  
  - **Notes:** —  

**Description:**  
Create a status log entry under `pm/status_logs/` summarizing:

- Current implementation progress for M03.  
- Any blocked tasks or open questions.  
- Any planned deferrals to later milestones.

---

### M03-T12 — Capture Human Decisions (Taxonomy Philosophy)

- **Type:** governance  
- **Depends On:** M03-T01 through M03-T10  
- **ETS Profiles:** —  
- **Status Block:**  
  - **Status:** pending  
  - **Last Updated:** —  
  - **Notes:** —  

**Description:**  
Record design decisions under `pm/decisions/` regarding:

- Naming conventions for Types and Domains (e.g., PascalCase codes).  
- Whether hard DELETE will be used in practice or reserved for rare cleanup scenarios.  
- UI treatment of deactivated vs deleted taxonomy values.  
- Any commitments about future hierarchy or tag systems.

---

## 4. Exit Criteria

M03 is considered complete when:

1. Type and Domain tables exist with schemas aligned to M03-T01/T02.  
2. EF-06 has optional `type_id` / `domain_id` fields and indexes in place.  
3. EF-07 exposes working taxonomy endpoints:
   - `GET/POST/PATCH/DELETE /api/types`  
   - `GET/POST/PATCH/DELETE /api/domains`  
4. UI can retrieve and use taxonomy for dropdowns and filters.  
5. ETS tests validate taxonomy correctness, resilience to deletes, and integration with EF-06.  
6. Status logs and taxonomy philosophy decisions are recorded under `pm/`.  
