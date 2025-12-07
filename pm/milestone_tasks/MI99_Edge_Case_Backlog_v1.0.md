# MI99 — Edge-Case & Decision Follow-Ups — v1.0

---

## 0. Metadata

- **Milestone ID:** MI99  
- **Milestone Name:** Edge-Case & Decision Follow-Ups  
- **Scope Summary:**  
  Track out-of-band tasks that fall outside the standard M01–M07/MG0x milestones but still require execution or monitoring. Initial focus: follow-ups from the ingestion-index decision (`pm/decisions/2025-12-06_ingestion_indexes.md`).  
- **Primary Components:**  
  - EF-06 EntryStore schema + metadata  
  - EF-01 CaptureService wiring  
  - EF-07 API capture contracts  
  - ETS validation coverage  
- **Related Artifacts:**  
  - `pm/decisions/2025-12-06_ingestion_indexes.md`  
  - `EF06_EntryStore_Spec_v1.1.md` + addendum  
  - `EF01_CaptureService_Interfaces_Spec_v1.1.md`  
  - `EF07_Api_Contract_v1.2.md`  

---

## 1. Status Tracking Guidance

Same field semantics as core milestones, but MI99 may be updated opportunistically as edge-cases emerge.

- **Status values:** `pending`, `in_progress`, `blocked`, `deferred`, `done`.  
- Update only the Status Block for each task when recording progress.  

Template:

```markdown
- **Status:** pending
- **Last Updated:** —
- **Notes:** —
```

---

## 2. Tasks

### MI99-T01 — Add Fingerprint Columns to `entries`

- **Type:** schema  
- **Depends On:** Decision MI99-D01 (ingestion indexes)  
- **Status Block:**
  - **Status:** pending  
  - **Last Updated:** —  
  - **Notes:** —  

**Description:**  
Extend EF-06 `entries` schema with `capture_fingerprint` (text) and `fingerprint_algo` (enum/text per EF06 addendum). Ensure migrations/spec updates reflect nullable/default behavior needed for backfill.

---

### MI99-T02 — Write Fingerprint Metadata from EF-01

- **Type:** implementation  
- **Depends On:** MI99-T01  
- **Status Block:**
  - **Status:** pending  
  - **Last Updated:** —  
  - **Notes:** —  

**Description:**  
Update EF-01 ingestion paths (watch folders, manual text, API `file_ref`) to compute fingerprints and persist both fingerprint and algorithm when creating entries.

---

### MI99-T03 — Document Indexes in EF06 Spec

- **Type:** documentation  
- **Depends On:** MI99-T01  
- **Status Block:**
  - **Status:** pending  
  - **Last Updated:** —  
  - **Notes:** —  

**Description:**  
Amend `EF06_EntryStore_Spec_v1.1.md` (or next rev) to list `IDX_entries_fingerprint_channel`, `IDX_entries_source_channel`, and `IDX_entries_source_path`, referencing decision MI99-D01.

---

### MI99-T04 — Validate Idempotency via ETS Profiles

- **Type:** testing  
- **Depends On:** MI99-T02, MI99-T03  
- **Status Block:**
  - **Status:** pending  
  - **Last Updated:** —  
  - **Notes:** —  

**Description:**  
Expand ETS profiles (EF01-WATCH, EF01-API) to prove the new indexes prevent duplicate entries and keep query plans efficient for replay scenarios.

---

## 3. Adding Future Edge-Case Tasks

New edge items can be appended as `MI99-T0x` entries with the same Status Block structure. Reference any upstream decision or spec change so the history of why the item exists remains clear.
