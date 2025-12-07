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
  - **Status:** done  
  - **Last Updated:** 2025-12-07 — GPT-5.1-Codex  
  - **Notes:** `backend/migrations/versions/20251207_add_capture_fingerprint_columns.py` adds the columns + supporting indexes per MI99-D01.  

**Description:**  
Extend EF-06 `entries` schema with `capture_fingerprint` (text) and `fingerprint_algo` (enum/text per EF06 addendum). Ensure migrations/spec updates reflect nullable/default behavior needed for backfill.

---

### MI99-T02 — Write Fingerprint Metadata from EF-01

- **Type:** implementation  
- **Depends On:** MI99-T01  
- **Status Block:**
  - **Status:** done  
  - **Last Updated:** 2025-12-07 — GPT-5.1-Codex  
  - **Notes:** Watcher/manual/API capture paths now call `EntryStoreGateway.create_entry` with `capture_fingerprint` + `fingerprint_algo` metadata (see `backend/app/domain/ef01_capture/*.py`, `backend/app/api/routers/capture.py`).  

**Description:**  
Update EF-01 ingestion paths (watch folders, manual text, API `file_ref`) to compute fingerprints and persist both fingerprint and algorithm when creating entries.

---

### MI99-T03 — Document Indexes in EF06 Spec

- **Type:** documentation  
- **Depends On:** MI99-T01  
- **Status Block:**
  - **Status:** done  
  - **Last Updated:** 2025-12-07 — GPT-5.1-Codex  
  - **Notes:** `project_scope/tactical/EF06_EntryStore_Spec_v1.1.md` now lists the fingerprint/source-path indexes with a reference to decision `2025-12-06_ingestion_indexes.md`.  

**Description:**  
Amend `EF06_EntryStore_Spec_v1.1.md` (or next rev) to list `IDX_entries_fingerprint_channel`, `IDX_entries_source_channel`, and `IDX_entries_source_path`, referencing decision MI99-D01.

---

### MI99-T04 — Validate Idempotency via ETS Profiles

- **Type:** testing  
- **Depends On:** MI99-T02, MI99-T03  
- **Status Block:**
  - **Status:** pending  
  - **Last Updated:** 2025-12-07 — GPT-5.1-Codex  
  - **Notes:** Blocking on new ETS coverage that exercises EF-01 watcher/API flows against the Postgres gateway once MI02 Postgres adapter is stable.  

**Description:**  
Expand ETS profiles (EF01-WATCH, EF01-API) to prove the new indexes prevent duplicate entries and keep query plans efficient for replay scenarios.

---

### MI99-T05 — Define Transcript Retention & Cleanup Policy

- **Type:** governance/process  
- **Depends On:** M02-T02b transcript externalization (decision `2025-12-07_m02_t02b_transcript_externalization.md`)  
- **Status Block:**
  - **Status:** pending  
  - **Last Updated:** 2025-12-07 — GPT-5.1-Codex  
  - **Notes:** New task; needs policy + automation design.  

**Description:**  
Codify how EF-02 transcript artifacts under `llm.whisper.transcript_output_root` are retained, rotated, or deleted so desktop installs do not grow unbounded. Deliverables: retention policy doc (linkable from EF06/INF01 specs), cleanup script or service hook tied to entry archival, and ETS guidance for verifying the process.

---

### MI99-T06 — Surface Whisper Configuration in EF-07 UI

- **Type:** UX follow-up  
- **Depends On:** M05 UI scaffolding, INF-01 charter for Whisper config  
- **Status Block:**
  - **Status:** pending  
  - **Last Updated:** 2025-12-07 — GPT-5.1-Codex  
  - **Notes:** Track requirement ahead of M05 so EF-07 desktop UI exposes Whisper enablement + transcript root.  

**Description:**  
Expose current Whisper/transcript settings inside the EF-07 desktop UI so operators can verify model/device, transcript output roots, and public URL mappings without leaving the app. This should land alongside the broader settings shell built in M05; document the UX intent here so it is not deferred post-M05.

---

## 3. Adding Future Edge-Case Tasks

New edge items can be appended as `MI99-T0x` entries with the same Status Block structure. Reference any upstream decision or spec change so the history of why the item exists remains clear.
